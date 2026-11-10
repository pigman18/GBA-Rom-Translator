#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""道具表 stride 40→48：字段偏移 +8 的可行性核查（逐点定性）。

## 为什么需要这一步

stride 扩到 48 后名字区 9B→17B，元数据整体后移 8 字节。
12 个访问函数读的是硬编码偏移，必须同步 +8，否则读到名字尾部。

难点：Thumb 的 `ldr/ldrb` 立即数是 5 位（0..31），`ldrh` 是 5 位×2（0..62）。
偏移 +8 后有 1 处（0x1C→0x24=36）超出 `ldrb` 范围，且该处前后没有
足够空间插 `adds r1,#8`，附近代码段也没有空洞放 trampoline 桩。

本脚本把每处的**可行改法**列清楚，供生成补丁时逐条处理。
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
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
SHIFT = 8

# (指令 GBA, mnemonic, 原偏移)
SITES = [
    (0x080A53B4, "ldrh", 0x0A),
    (0x080A53D8, "ldrh", 0x0C),
    (0x080A53FC, "ldrb", 0x0E),
    (0x080A5420, "ldrb", 0x0F),
    (0x080A5432, "adds", 0x10),   # adds r4,#0x10 → #0x18
    (0x080A546C, "ldrb", 0x14),
    (0x080A5490, "ldrb", 0x15),
    (0x080A54B4, "ldrb", 0x16),
    (0x080A54D8, "ldrb", 0x17),
    (0x080A54EA, "adds", 0x18),   # adds r4,#0x18 → #0x20
    (0x080A5524, "ldrb", 0x1C),   # ★ 0x24 超 ldrb 上限
    (0x080A5536, "adds", 0x20),   # adds r4,#0x20 → #0x28
]


def main() -> int:
    rom = ROM.read_bytes()
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

    print(f"元数据后移 {SHIFT}B")
    print("=" * 88)
    print(f"{'指令地址':<12}{'形式':<10}{'原偏移':>6}{'新偏移':>7}  改法")
    print("-" * 88)
    for gba, mn, old in SITES:
        new = old + SHIFT
        off = gba - 0x08000000
        ins = list(md.disasm(rom[off:off + 2], gba))
        got = f"{ins[0].mnemonic} {ins[0].op_str}" if ins else "?"
        if mn == "adds":
            how = f"改 adds 立即数 #{old + SHIFT:#x}（2B 原地）"
        elif mn == "ldrb":
            how = ("改 5 位立即数（2B 原地）" if new <= 31
                   else "★ 超 ldrb 上限 31，需特殊处理")
        elif mn == "ldrh":
            how = ("改 5 位立即数×2（2B 原地）" if new // 2 <= 31
                   else "★ 超 ldrh 上限 62")
        else:
            how = "?"
        print(f"0x{gba:08X}  {mn:<10}0x{old:02X}{new:>#8x}  {how}")
        print(f"            现指令: {got}")

    print()
    print("★ 唯一难点 0x080A5524：ldrb r0,[r1,#0x1c] → 需要 #0x24(36) > 31")
    print("  该处上下文：")
    for x in md.disasm(rom[0x0A551C:0x0A5530], 0x080A551C):
        print(f"    0x{x.address:08X}  {x.mnemonic:7s} {x.op_str}")
    print()
    print("  解决思路（按代价从低到高）：")
    print("   A. 让 0x1C 字段在新表里**不后移**：把该字段放在新 entry 的 0x1C，")
    print("      代价是名字区只能扩到 0x1C-1 = 27B 上限，但字段 0x14..0x17 会冲突。")
    print("   B. 用 add sp / 寄存器中转：附近无 2 字节空隙，不可行。")
    print("   C. 把 ldrb 换成 ldrh+掩码：需要 2 条指令 4 字节，覆盖 pop{r4}，")
    print("      可在桩里恢复 pop 语义（桩自己 pop 并跳回）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
