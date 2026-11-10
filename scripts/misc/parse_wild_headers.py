#!/usr/bin/env python3
"""把 gWildMonHeaders 按「结构推断」解析出来，并明确标注哪些是猜的。

⚠ 本脚本的结论**只作为线索**，不作为改 ROM 的依据。
   实测教训：gWildMonHeaders 的表项并不是简单的 (mapGroup,mapNum)+索引，
   28 字节里混着地形行为表（0xA1A8..0xA6A2 一串）和指向别处的指针
   （0x08399F6D / 0x08399F8E …）。在没把结构完全定死之前改它，
   极可能把别的数据改坏。

用法：python scripts/parse_wild_headers.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BASE = 0x08000000
TABLE = 0x0839D454
SIZE = 0x7A8
STEP = 0x1C


def u32(b, o):
    return int.from_bytes(b[o:o + 4], "little")


def main() -> int:
    rom = ROM.read_bytes()
    off = TABLE - BASE
    blob = rom[off:off + SIZE]

    print(f"gWildMonHeaders @0x{TABLE:08X}  {SIZE}B  步长假设=0x{STEP:X}")
    print(f"{'i':>3} {'+off':>6}  {'前8B':<24} {'ptr@+12':<12} {'ptr@+20':<12}")
    for i in range(0, SIZE, STEP):
        head = blob[i:i + 8].hex(" ")
        p1 = u32(blob, i + 12)
        p2 = u32(blob, i + 20)
        s1 = f"0x{p1:08X}" if 0x08000000 <= p1 < 0x0A000000 else "     -   "
        s2 = f"0x{p2:08X}" if 0x08000000 <= p2 < 0x0A000000 else "     -   "
        if i % (STEP * 4) == 0 or i < 4:
            print(f"{i // STEP:>3} +0x{i:04X}  {head:<24} {s1:<12} {s2:<12}")

    print("\n结论：")
    print("  · 每条 28 字节，前 8 字节形如 <terrain> <terrain> ... 0xFF 0xFF")
    print("  · +12 / +20 是指向 0x0839xxxx 的指针（真实数据在别处）")
    print("  · mapGroup/mapNum 不在表项开头 ⇒ 表不是按地图直接下标")
    print("  ⚠ 数据结构未完全确认前，不要改这张表。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
