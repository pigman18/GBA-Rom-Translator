#!/usr/bin/env python3
"""只读 ROM + 符号表，定位招式名表的真实位置。

已确认：
  0x1CAD04 起的内容是「1a 10 08 ff / 06 27 13 61 86 a0 9d ff」这类短串，
  stride=8 合规率仅 26%，不是招式名表。
  真正的名字表区在 0x1CA354（宝可梦名，stride=6，合规 100%）。

符号表 gMoveNames = 0x081C8DC8，size 0x1207 = 4615 B。
354 项 → 4615/354 ≈ 13.03 → stride 13。
本脚本从 0x1C8DC8 读 354×13，验证 FF 填充合规率，并与 0x1CAD04 对比。

用法：
    python scripts/research/ruby/probe_movenames_sym.py
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
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

GBA_BASE = 0x08000000

# 符号表给出的候选
CANDIDATES = [
    ("gMoveNames(符号)", 0x1C8DC8, 0x1207),
    ("gSpeciesNames(符号)", 0x1C7C14, 0x11B4),
    ("gAbilityNames(符号)", 0x1CACF0, 0),
    ("texts.json 招式名", 0x1CAD04, 0),
    ("texts.json 宝可梦名", 0x1CA354, 0),
]


def dump(rom: bytes, off: int, n: int = 96) -> None:
    for r in range(0, n, 24):
        print(f"    0x{off + r:06X}: " + rom[off + r:off + r + 24].hex(" "))


def compliance(rom: bytes, base: int, stride: int, n: int) -> float:
    ok = total = 0
    for i in range(n):
        off = base + i * stride
        if off + stride > len(rom):
            break
        seg = rom[off:off + stride]
        total += 1
        ff = seg.find(0xFF)
        if ff >= 0 and all(b == 0x00 for b in seg[ff + 1:]):
            ok += 1
    return ok / total if total else 0.0


def main() -> int:
    rom = ROM.read_bytes()
    print(f"ROM {len(rom):,} B\n")

    for label, off, size in CANDIDATES:
        print(f"=== {label}  0x{off:06X}  size=0x{size:X} ===")
        dump(rom, off)
        if size:
            for n_items in (354, 411, 412):
                s = size / n_items
                if abs(s - round(s)) < 0.3:
                    st = round(s)
                    r = compliance(rom, off, st, min(n_items, 100))
                    print(f"    size/{n_items} → stride≈{st}, FF 后全 0 合规 {r:.0%}")
        # 自由找最佳 stride
        best = max(((compliance(rom, off, s, 100), s) for s in range(4, 20)))
        print(f"    最佳 stride={best[1]}  合规 {best[0]:.0%}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
