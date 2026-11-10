#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统计产物 ROM 里 9 张定长表到底有多少项真的写成了中文。

## 为什么要这个脚本

2026-11-05 用户质问：「你之前不是给了我一堆 100% 的表格吗？为什么到现在
还是几千几千条没有写入？」

这两个数字说的不是同一件事：

  · 之前那张 100% 表 = **stride 站点识别率**（反汇编找出「读这张表」的
    乘法指令，并确认改立即数能算对新 stride）。它证明的是「我知道怎么改
    表结构」，**不证明表里有中文**。
  · build.json 的 keep 计数 = **注入决策**（这条文本走哪条通路），
    对定长表来说，它们走的是 asm 通道（gen/table_data.asm），
    所以 build.json 里显示 keep 是**预期行为**，不构成缺口。

真实答案只能从产物 ROM 里逐项读出来 —— 这就是本脚本做的事。

用法：
    python scripts/research/ruby/count_table_zh.py [rom_path]
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ROM = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"

# 表地址**不要硬编码** —— 它们每次重新生成都会变（新区按顺序分配）。
# 直接从 gen/table_data.asm 里读 .org + TblXxx 标签。
# (标签, 项数, stride, name_offset, eos, usable)
TABLE_SPEC = [
    ("TblMoveNames",       354, 32,  0, 0xFF, 32),
    ("TblSpeciesCategory", 386, 28,  6, 0x00,  6),
    ("TblItemNames",       348, 48,  0, 0xFF, 17),
    ("TblDecorNames",      120, 28, 13, 0xFF, 10),
    ("TblAbilityNames",     77, 32,  0, 0xFF, 32),
    ("TblTypeNames",        18, 20,  0, 0xFF, 20),
    ("TblSpeciesNames",    412, 24,  0, 0xFF, 24),
    ("TblAbilityDesc",      78, 48,  0, 0xFF, 48),
    ("TblBerryNames",       43, 28,  0, 0xFF, 10),
]

AND_ASM = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook" / "gen" / "table_data.asm"


def load_tables() -> list:
    """从 gen/table_data.asm 读出每张表的实际 .org 地址。"""
    import re
    labels: dict[str, int] = {}
    if AND_ASM.is_file():
        src = AND_ASM.read_text(encoding="utf-8")
        for m in re.finditer(r"\.org\s+(0x[0-9A-Fa-f]+)\s*\n\.align\s+4\s*\n(\w+):", src):
            labels[m.group(2)] = int(m.group(1), 16)
    out = []
    for sym, n, stride, noff, eos, usable in TABLE_SPEC:
        gba = labels.get(sym)
        if gba is None:
            print(f"[warn] table_data.asm 里找不到 {sym}，跳过")
            continue
        out.append((sym, gba, n, stride, noff, eos, usable))
    return out


def classify(rom: bytes, gba: int, stride: int, noff: int,
             eos: int, usable: int) -> str:
    """单表项判定：中文 / 日文 / 空。

    中文判据：name 区前 4 字节内出现 0xF9（F9 00 hi lo 单字编码）。
    日文判据：name 区有内容但不是 F9（原版 PCS 假名）。
    空判据：name 区全是 eos / 0x00。
    """
    base = gba - 0x08000000
    off = base + noff
    seg = rom[off:off + usable]
    if not seg:
        return "空"
    if 0xF9 in seg[:4] or seg[:1] == b"\xF9":
        return "中"
    if all(b in (eos, 0x00) for b in seg):
        return "空"
    return "日"


def main() -> int:
    rom_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ROM
    if not rom_path.is_file():
        print(f"[ERR] ROM 不存在: {rom_path}")
        return 3
    rom = rom_path.read_bytes()
    print(f"[rom] {rom_path.name}  {len(rom):,} B\n")

    hdr = f"{'表':<16}{'项数':>6}{'中文':>7}{'日文':>7}{'空':>7}   中文率"
    print(hdr)
    print("-" * len(hdr))
    tot = {"中": 0, "日": 0, "空": 0}
    total_n = 0
    for name, gba, n, stride, noff, eos, usable in load_tables():
        c = {"中": 0, "日": 0, "空": 0}
        for i in range(n):
            base = gba - 0x08000000
            off = base + i * stride + noff
            seg = rom[off:off + usable]
            if not seg:
                c["空"] += 1
                continue
            if seg[:1] == b"\xF9" or 0xF9 in seg[:4]:
                c["中"] += 1
            elif all(b in (eos, 0x00) for b in seg):
                c["空"] += 1
            else:
                c["日"] += 1
        rate = 100.0 * c["中"] / n if n else 0.0
        print(f"{name:<16}{n:>6}{c['中']:>7}{c['日']:>7}{c['空']:>7}   {rate:5.1f}%")
        for k in tot:
            tot[k] += c[k]
        total_n += n

    print("-" * len(hdr))
    rate = 100.0 * tot["中"] / total_n if total_n else 0.0
    print(f"{'合计':<16}{total_n:>6}{tot['中']:>7}{tot['日']:>7}{tot['空']:>7}   {rate:5.1f}%")
    print()
    print("说明：「中」= 已写入 F9 单字中文编码；「日」= 仍是原版日文；")
    print("      「空」= 该表此项本身为空条目（游戏里无对应数据）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
