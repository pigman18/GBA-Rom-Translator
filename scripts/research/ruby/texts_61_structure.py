#!/usr/bin/env python3
"""texts_61: 0x3B3E64 表的上下文结构 —— 它夹在两片 u16 索引数组中间。

texts_60 发现：
  · 22 项地址单调递增，按假名排序 → 是词库里的连续段
  · 表前 0x3B3E24..0x3B3E64 是 u16 数组（b3 00 b4 00 31 00 72 00 ...）
  · 表后 0x3B3EBC.. 也是 u16 数组

这些 u16 是什么？如果是词条索引，说明「u16 索引数组 + 指针表」共同构成一个索引结构。

本脚本：
  1. 把表前/表后的 u16 数组解码，看数值范围是否在 0..926（词条数）
  2. 若是索引，验证「指针表[i] 对应的词条序号 == 附近 u16 值」
  3. 判定整个结构：这很可能是「假名索引 → 词条」的查找表

用法: python scripts/research/ruby/texts_61_structure.py
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
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BASE = 0x08000000
TABLE = 0x3B3E64


def main() -> int:
    rom = ROM_PATH.read_bytes()

    print("=" * 112)
    print("1) 表前 u16 数组（0x3B3E24..0x3B3E64，共 32 个 u16）")
    print("=" * 112)
    vals = [struct.unpack_from("<H", rom, a)[0]
            for a in range(TABLE - 0x40, TABLE, 2)]
    print(f"  {vals}")
    print(f"  min={min(vals)} max={max(vals)}  （词库 926 条，若 max<926 则可能是词条索引）")

    print()
    print("=" * 112)
    print("2) 表后 u16 数组（0x3B3EBC..0x3B3EFC，共 32 个）")
    print("=" * 112)
    vals2 = [struct.unpack_from("<H", rom, a)[0]
             for a in range(0x3B3EBC, 0x3B3EFC, 2)]
    print(f"  {vals2}")
    print(f"  min={min(vals2)} max={max(vals2)}")

    print()
    print("=" * 112)
    print("3) 更大范围看这两个数组的边界")
    print("=" * 112)
    # 向前找，看 u16 数组从哪开始（值都 < 1000 视为索引数组）
    a = TABLE
    while a > TABLE - 0x400:
        v = struct.unpack_from("<H", rom, a - 2)[0]
        if v >= 1000:
            break
        a -= 2
    print(f"  表前索引数组起点: 0x{a:06X}（长度 {(TABLE - a)//2} 个 u16）")
    # 向后
    b = TABLE + 22 * 4
    start_b = b
    while b < TABLE + 0x400:
        v = struct.unpack_from("<H", rom, b)[0]
        if v >= 1000:
            break
        b += 2
    print(f"  表后索引数组 0x{start_b:06X}..0x{b:06X}（长度 {(b - start_b)//2} 个 u16）")

    print()
    print("=" * 112)
    print("4) 判定：32 个 u16 分别对应什么")
    print("=" * 112)
    print("  已知假名顺序：あ=1 い=2 う=3 え=4 お=5 か=6 き=7 く=8 ...")
    print("  若表前 32 个 u16 是「每个假名行首词条的索引」，应与词库排序一致")
    print()
    # 词库按假名排序，取首假名
    import sys as _s2
    _s2.path.insert(0, str(ROOT / "src"))
    from meowth.jp_pcs import decode_pcs

    segs = []
    start = 0x3B219B
    for i in range(0x3B219B, 0x3B3900):
        if rom[i] == 0xFF:
            t = decode_pcs(rom[start:i + 1])
            if t:
                segs.append((start, t))
            start = i + 1
    print(f"  词库 {len(segs)} 条，前 40 条的首字：")
    for k, (o, t) in enumerate(segs[:40]):
        print(f"    [{k:>3}] 0x{o:06X} {t[0]!r}  {t!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
