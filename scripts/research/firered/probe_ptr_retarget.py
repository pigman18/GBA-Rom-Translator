#!/usr/bin/env python3
"""火红日文名称表的「指针是否被改指新表」实测。

已确认：火红 0x3A0000..0x3C0000 等日文名表区，两版差异仅 1.1%（局部小改），
主体原样保留 → 与 FIRERED_FULL_LOGIC §2.2「原串留孤儿」一致。

本脚本回答最后一环：那些日文名表的**指针**被改到哪了？
  - 若指针改指 0x6D0000..0x730000 的新中文表 → 整表搬走 + 改指针
  - 若指针没动 → 靠运行时翻译层（hook）替换

做法：在汉化版里找指向新中文区（0x6D0000..0x730000）的 u32 指针数量，
      与指向原日文名表区的指针数量对比。

用法：
    python scripts/research/firered/probe_ptr_retarget.py
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

GBA_BASE = 0x08000000
NEW_ZH = (0x6D0000, 0x730000)   # 汉化新增中文区
JP_NAMES = (0x3A0000, 0x3C0000)  # 原版日文名表区


def count_ptrs_into(rom: bytes, lo: int, hi: int) -> tuple[int, list[int]]:
    """统计指向 [lo,hi) 的 u32 指针数量，返回 (数量, 前若干来源偏移)。"""
    cnt = 0
    srcs = []
    for off in range(0, len(rom) - 4, 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            t = v - GBA_BASE
            if lo <= t < hi:
                cnt += 1
                if len(srcs) < 10:
                    srcs.append(off)
    return cnt, srcs


def main() -> int:
    a = ORIG.read_bytes()
    b = ZH.read_bytes()

    print("=== 指向「汉化新增中文区」0x6D0000..0x730000 的指针 ===")
    for tag, rom in (("原版", a), ("汉化", b)):
        n, srcs = count_ptrs_into(rom, *NEW_ZH)
        print(f"  {tag}: {n} 个" + (f"  前几处 {[f'0x{s:X}' for s in srcs[:6]]}" if n else ""))

    print("\n=== 指向「原版日文名表区」0x3A0000..0x3C0000 的指针 ===")
    for tag, rom in (("原版", a), ("汉化", b)):
        n, srcs = count_ptrs_into(rom, *JP_NAMES)
        print(f"  {tag}: {n} 个" + (f"  前几处 {[f'0x{s:X}' for s in srcs[:6]]}" if n else ""))

    print("\n=== 指针差值分析（汉化 - 原版）===")
    n_new_a, _ = count_ptrs_into(a, *NEW_ZH)
    n_new_b, _ = count_ptrs_into(b, *NEW_ZH)
    n_jp_a, _ = count_ptrs_into(a, *JP_NAMES)
    n_jp_b, _ = count_ptrs_into(b, *JP_NAMES)
    print(f"  新增中文区被引用: {n_new_a} → {n_new_b}  (Δ{n_new_b - n_new_a:+d})")
    print(f"  日文名表区被引用: {n_jp_a} → {n_jp_b}  (Δ{n_jp_b - n_jp_a:+d})")
    if n_new_b > n_new_a and n_jp_b < n_jp_a:
        print("  ⇒ 指针被批量改指新中文区 = 整表搬走 + 改指针")
    elif n_new_b > n_new_a:
        print("  ⇒ 新增引用指向中文区，但日文名表指针未减 = 混合策略")
    else:
        print("  ⇒ 无批量改指，靠运行时替换或逐条改")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
