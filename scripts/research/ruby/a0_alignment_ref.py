#!/usr/bin/env python3
"""A0 关键参照：火红的文本指针是 4 对齐还是任意对齐？

若火红（成功的汉化）的指针大量是非 4 对齐，说明「必须 4 对齐」这条规则是错的；
若几乎都是 4 对齐，说明我们的过滤是对的，2,781 条非对齐确实是巧合。

用法：
    python scripts/research/ruby/a0_alignment_ref.py
"""
from __future__ import annotations

import struct
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
FR_ORIG = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
RB_ORIG = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

GBA_BASE = 0x08000000
# 火红中文文本区
FR_TEXT = [(0x6D0000, 0x730000), (0xAF5000, 0xB00000)]


def analyze_align(rom: bytes, zones: list[tuple[int, int]], label: str) -> None:
    """统计指向 zones 的指针，按 4 对齐/非对齐分类。"""
    al = 0
    un = 0
    un_samples = []
    for off in range(0, len(rom) - 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if not (GBA_BASE <= v < 0x0A000000):
            continue
        t = v - GBA_BASE
        if not any(lo <= t < hi for lo, hi in zones):
            continue
        if off & 3:
            un += 1
            if len(un_samples) < 5:
                un_samples.append(off)
        else:
            al += 1
    total = al + un
    print(f"=== {label} ===")
    print(f"  指向目标区的 u32 总数: {total:,}")
    print(f"  4 字节对齐:   {al:,} ({al/max(total,1):.1%})")
    print(f"  非 4 对齐:    {un:,} ({un/max(total,1):.1%})")
    if un_samples:
        print(f"  非对齐样本: " + ", ".join(f"0x{x:X}" for x in un_samples))
    print()


def main() -> int:
    fr_o = FR_ORIG.read_bytes()
    fr_z = FR_ZH.read_bytes()
    rb_o = RB_ORIG.read_bytes()

    analyze_align(fr_z, FR_TEXT, "火红汉化 → 中文文本区")

    # 火红原版 → 原版日文文本区（用同一区域范围作对照）
    analyze_align(fr_o, FR_TEXT, "火红原版 → 同区域（原版是空白，应极少）")

    # ruby 原版 → 已知名称表区
    RB_ZONES = [(0x1CA000, 0x1CC000)]
    analyze_align(rb_o, RB_ZONES, "ruby 原版 → 名称表区")

    print("=== 结论判据 ===")
    print("  火红若绝大多数是 4 对齐 → 我们的 4 对齐过滤是对的")
    print("  火红若非对齐占比高   → 4 对齐规则过严，需要放宽")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
