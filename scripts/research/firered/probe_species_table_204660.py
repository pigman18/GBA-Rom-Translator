#!/usr/bin/env python3
"""检查火红原版物种名表 0x204660 的内容与汉化改动。

已确认：31 处代码位置在原版指向 0x204660，汉化指向 0x71F444。
0x204660 区域汉化差异 0/4096（原样保留），但它被引用的次数从 32 降到 1。

用法：
    python scripts/research/firered/probe_species_table_204660.py
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
ORIG = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"

BASE = 0x204660


def main() -> int:
    a = ORIG.read_bytes()
    b = ZH.read_bytes()

    print(f"=== 原版 0x{BASE:06X} 起，按 11 字节/项 ===")
    for k in range(20):
        seg = a[BASE + k * 11:BASE + k * 11 + 11]
        print(f"  item{k:>2}: {seg.hex(' ')}")

    print(f"\n=== 汉化版同位置 ===")
    for k in range(20):
        seg = b[BASE + k * 11:BASE + k * 11 + 11]
        print(f"  item{k:>2}: {seg.hex(' ')}")

    print()
    for span, label in ((412 * 11, "412 项 × 11B"), (0x1000, "4KB")):
        d = sum(1 for x, y in zip(a[BASE:BASE + span], b[BASE:BASE + span]) if x != y)
        print(f"  {label:<12} 差异 {d:,}/{span:,} ({d/span:.1%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
