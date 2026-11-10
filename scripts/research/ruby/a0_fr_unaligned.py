#!/usr/bin/env python3
"""火红 2,919 个非对齐指针是什么？——判断 4 对齐规则的边界。

上一脚本：
  火红汉化 → 中文区 u32 共 10,821 个，其中 4 对齐 7,902（73.0%），非对齐 2,919（27.0%）
  火红原版 → 同区     共 440 个，其中 4 对齐 36（8.2%），非对齐 404（91.8%）

若非对齐的那些是代码巧合，它们在原版里也应该存在（同样的巧合位置）。
本脚本对比「同一个非对齐位置」在原版是否也"恰好"等于同一地址。

用法：
    python scripts/research/ruby/a0_fr_unaligned.py
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
FR_ORIG = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"

GBA_BASE = 0x08000000
FR_TEXT = [(0x6D0000, 0x730000), (0xAF5000, 0xB00000)]
CODE_END = 0x200000


def collect(rom: bytes, zone: list[tuple[int, int]], aligned: bool) -> dict[int, int]:
    out = {}
    for off in range(0, len(rom) - 4):
        if bool(off & 3) == aligned:
            continue
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            t = v - GBA_BASE
            if any(lo <= t < hi for lo, hi in zone):
                out[off] = t
    return out


def main() -> int:
    a = FR_ORIG.read_bytes()
    b = FR_ZH.read_bytes()

    un_zh = collect(b, FR_TEXT, aligned=False)
    un_orig = collect(a, FR_TEXT, aligned=False)

    print(f"火红汉化 非对齐站点: {len(un_zh):,}")
    print(f"火红原版 非对齐站点: {len(un_orig):,}")
    both = set(un_zh) & set(un_orig)
    print(f"两边都有的位置:      {len(both):,} ({len(both)/max(len(un_zh),1):.1%})")
    print()
    print("  若两边都有的占比高 → 原版就有同样的巧合，说明这些是代码巧合，不是真指针")
    print("  若很低 → 汉化新增了这些非对齐指针，说明确实在用")
    print()

    print("=== 非对齐站点按区域分布（汉化）===")
    code = [o for o in un_zh if o < CODE_END]
    data = [o for o in un_zh if o >= CODE_END]
    print(f"  代码段 <0x{CODE_END:X}:  {len(code):,}")
    print(f"  数据区:            {len(data):,}")
    print()

    print("=== 样本对比（汉化 vs 原版同位置）===")
    shown = 0
    for off, tgt in sorted(un_zh.items()):
        if shown >= 10:
            break
        if off + 4 > len(a):
            continue
        va = struct.unpack_from("<I", a, off)[0]
        vb = struct.unpack_from("<I", b, off)[0]
        ctx_a = a[max(0, off - 6):off + 8]
        ctx_b = b[max(0, off - 6):off + 8]
        print(f"  0x{off:06X}  原版 0x{va:08X} → 汉化 0x{vb:08X}")
        print(f"    原版上下文: {ctx_a.hex(' ')}")
        print(f"    汉化上下文: {ctx_b.hex(' ')}")
        shown += 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
