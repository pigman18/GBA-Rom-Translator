#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""道具表 stride 放大：找出全部需要改乘法的指令站点。

## 结论来源（2026-11-05 实测，已排除其它路线）

1. 道具名**没有独立名字指针**：
   entry +0x10 / +0x18 两个指针实测都指向**说明文本**
   （`ポケモンを かならず つかまえる…`），不是名字。

2. 名字只存在 entry 开头 0..8 这 9 字节（8B 内容 + FF），
   `+9` 之后紧跟 u16/u8 字段，**没有可挪的空隙**。

3. 中文 2 字 = `f9 00 xxxx` ×2 + FF = **9B**，刚好等于 9B 槽；
   但 281 条译文里只有 13 条 ≤2 字，其余 268 条都是 3~6 字（13~29B）。

⇒ 只能扩大 stride。游戏访问这张表的方式是
   `(id*4 + id) * 8 + base` = id×40，全部编译进代码，
   所以必须把每一处 ×40 改成 ×48。

本脚本把这 14 个站点的**改前/改后机器码**打印出来，供生成 armips 补丁。

用法：
    python scripts/research/ruby/plan_item_stride.py
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
BASE_GBA = 0x0839A648
OLD_STRIDE = 40
NEW_STRIDE = 48


def main() -> int:
    rom = ROM.read_bytes()
    pat = struct.pack("<I", BASE_GBA)
    sites: list[int] = []
    i = rom.find(pat)
    while i != -1:
        sites.append(i)
        i = rom.find(pat, i + 1)

    print(f"道具表基址 0x{BASE_GBA:08X}  字面量站点 {len(sites)} 处")
    print(f"stride {OLD_STRIDE} -> {NEW_STRIDE}")
    print()
    print("每处站点前 0x14 字节的指令（找 ×40 的展开：lsls#2 / adds / lsls#3）")
    print("-" * 84)

    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

    patch_sites = []
    for s in sites:
        start = s - 0x14
        print(f"\n[站点 0x{s + 0x08000000:08X}]")
        seq = list(md.disasm(rom[start:s + 4], start + 0x08000000))
        for x in seq:
            mark = ""
            if x.mnemonic == "lsls" and x.op_str == "r1, r1, #3":
                mark = "  <== ×40 的最后一乘（8→ stride）"
                patch_sites.append((x.address, "r1"))
            if x.mnemonic == "lsls" and x.op_str == "r0, r0, #3":
                mark = "  <== ×40 的最后一乘（8→ stride）"
                patch_sites.append((x.address, "r0"))
            print(f"  0x{x.address:08X}  {x.mnemonic:8s} {x.op_str}{mark}")

    print()
    print("=" * 84)
    print(f"需要把 lsls #3 改成 #? 的站点：{len(patch_sites)} 处")
    print()
    print("×40 = (id*4 + id) * 8。要变 ×48 = (id*4 + id) * 8 无法直接得到 48；")
    print("48 = 3 × 16 → 可改写成 (id*4 + id) = id*5，再 ×? 也不行。")
    print("⇒ 只能在 (id*4+id) 之后改用「乘 48」的新序列，或让 id 先乘 6 再乘 8：")
    print("     lsls r1,r0,#1 ; adds r1,r1,r0  → r1 = 3i")
    print("     lsls r1,r1,#4                 → r1 = 48i")
    print("   即把 (lsls#2 / adds / lsls#3) 换成 (lsls#1 / adds / lsls#4)，")
    print("   指令条数相同、总字节相同（6 字节），可原地替换。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
