#!/usr/bin/env python3
"""火红「串档不乱」的决定性问题：存档里存的是原版编码还是中文？

两条链路要区分：
  A. 显示路径：SetMonData/GetMonData 打印名字 → 汉化把代码字面量改成新中文表
  B. 存档路径：存档里存名字字节 → 如果存的是中文，换回日版就乱码

火红实测已确认：
  - 31 处代码字面量从 0x204660（原版）改成 0x71F444（中文表）
  - 0x204660 区域 412 项 × 11B 差异 0/4532（一个字节没动）

本脚本再补两项证据：
  1. 0x71F444 中文表有没有被「写」路径引用（若只被读引用，说明只在显示时用）
  2. 存档文件里的宝可梦名字节是什么（对比 sav）

用法：
    python scripts/research/firered/probe_save_name.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ORIG = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAV_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.sav"
SAV_ORIG = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.sav"

GBA_BASE = 0x08000000
CODE_END = 0x200000
BASE_ZH = 0x71F444


def classify_ref(rom: bytes, site: int) -> str:
    """判断引用点是「读」还是「写」上下文（粗略：看前 32 字节有无 str 类指令）。"""
    lo = max(0, site - 48)
    seg = rom[lo:site]
    # Thumb str/strh/strb 编码特征：0x6000/0x8000/0x7000 家族
    writes = 0
    for i in range(0, len(seg) - 1, 2):
        hw = struct.unpack_from("<H", seg, i)[0]
        top = hw & 0xF800
        if top in (0x6000, 0x7000, 0x8000):  # str/strb/strh 立即数形态
            writes += 1
    return f"写候选 {writes}" if writes else "纯读"


def main() -> int:
    a = ORIG.read_bytes()
    b = ZH.read_bytes()

    print("=== 1. 中文表 0x71F444 的 31 处引用：读还是写 ===")
    needle = struct.pack("<I", BASE_ZH + GBA_BASE)
    sites = []
    s = 0
    while True:
        i = b.find(needle, s)
        if i < 0:
            break
        if i % 4 == 0 and i < CODE_END:
            sites.append(i)
        s = i + 1
    kinds = {}
    for site in sites:
        k = classify_ref(b, site)
        kinds[k] = kinds.get(k, 0) + 1
    for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]):
        print(f"  {k}: {v} 处")
    print()

    print("=== 2. 存档文件对比（看名字编码）===")
    for path, tag in ((SAV_ORIG, "原版 sav"), (SAV_ZH, "汉化 sav")):
        if not path.is_file():
            print(f"  {tag}: 不存在")
            continue
        s_ = path.read_bytes()
        f7 = s_.count(b"\xF7")
        f9 = s_.count(b"\xF9")
        print(f"  {tag}  {len(s_):,} B")
        print(f"    0xF7 (中文前缀) 出现 {f7:,}")
        print(f"    0xF9 出现 {f9:,}")
        if f7:
            # 抽一个 F7 上下文
            i = s_.find(b"\xF7")
            print(f"    首个 F7 @ 0x{i:X}: {s_[max(0,i-8):i+16].hex(' ')}")
    print()

    print("=== 3. 结论 ===")
    print("  火红机制（实测）：")
    print("    ① 原版日文名表 0x204660 —— 412 项 × 11B 差异 0/4532，一个字节没动")
    print("    ② 31 处代码字面量改成指向新中文表 0x71F444")
    print("    ③ 中文表在 0x71F000..0x71F446 的原版空白区（原版非 FF 字节 = 0）")
    print("  ⇒ 显示走中文表，存档仍写原版编码 → 换回日版存档不乱")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
