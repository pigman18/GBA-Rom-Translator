#!/usr/bin/env python3
"""只读 ROM，独立反推各名称表的真实几何（不读 texts.json）。

背景：texts.json 的 stride/entry_size 是为「全 replace+slt2」妥协出来的，
       不能作为事实。前几支脚本用 texts.json 的 stride 算条目地址，
       那是循环论证。本脚本完全从 ROM 字节反推。

判据（定长补位表）：
  若表以 stride S 排列，则对每一项 i：
    - ROM[base + i*S + k] 从某个位置开始应为 0x00 填充
    - 且该项内首个 0xFF 之后到下一项之间应为 0x00（或 0xFF）
  对候选 S 打分，看哪个 S 让「FF 后全是 0x00 填充」的比例最高。

用法：
    python scripts/research/ruby/probe_geometry_from_rom.py
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

# 已验证首条文本的地址（字节级确认过：はたく / あくしゅう / ノーマル ...）
BASES = [
    ("招式名", 0x1CAD04, 354),
    ("特性名", 0x1CBC4C, 77),
    ("属性名", 0x1CBB0C, 18),
    ("宝可梦名", 0x1CA354, 412),
]


def score_stride(rom: bytes, base: int, stride: int, n: int) -> tuple[float, int, int]:
    """对 (base, stride) 打分：FF 后补 0 的比例 + 有效项数。"""
    ok = 0
    total = 0
    empty = 0
    for i in range(n):
        off = base + i * stride
        if off + stride > len(rom):
            break
        seg = rom[off:off + stride]
        total += 1
        ff = seg.find(0xFF)
        if ff < 0:
            continue
        if ff == 0:
            empty += 1
        tail = seg[ff + 1:]
        if all(b == 0x00 for b in tail):
            ok += 1
    if not total:
        return 0.0, 0, 0
    return ok / total, total, empty


def main() -> int:
    rom = ROM.read_bytes()
    print(f"ROM {len(rom):,} B  （不读 texts.json）\n")

    for name, base, n in BASES:
        print(f"=== {name} ===  基址 0x{base:06X}  预期项数 {n}")
        print("  原始字节（前 96B）:")
        for r in range(0, 96, 24):
            print(f"    0x{base + r:06X}: " + rom[base + r:base + r + 24].hex(" "))

        print("  候选 stride 打分（FF 后全 0 的比例）:")
        results = []
        for s in range(3, 25):
            ratio, total, empty = score_stride(rom, base, s, min(n, 200))
            results.append((ratio, s, total, empty))
        for ratio, s, total, empty in sorted(results, reverse=True)[:5]:
            print(f"    stride={s:>2}  合规 {ratio:5.1%}  （{total} 项，其中空项 {empty}）")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
