#!/usr/bin/env python3
"""只读 ROM，定位招式名表的真实起点与结构（不信任 texts.json）。

疑点：
  - 特性名 0x1CBC4C stride=8 合规 100%
  - 宝可梦名 0x1CA354 stride=6 合规 100%
  - 招式名 0x1CAD04 stride=8 只有 26%  ← texts.json 给的位置可能是错的

做法：
  1. 在 0x1CA000..0x1CC000 区间，对每个候选起点 × 候选 stride，
     算「FF 后全 0x00 填充」的合规率，找 100% 的组合
  2. 打印找到的组合及其前几项字节

用法：
    python scripts/research/ruby/probe_movenames_truth.py
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

LO, HI = 0x1CA000, 0x1CC000
N_CHECK = 60  # 检查前 N 项


def compliance(rom: bytes, base: int, stride: int, n: int) -> float:
    ok = 0
    total = 0
    for i in range(n):
        off = base + i * stride
        if off + stride > len(rom):
            break
        seg = rom[off:off + stride]
        total += 1
        ff = seg.find(0xFF)
        if ff < 0:
            continue
        if all(b == 0x00 for b in seg[ff + 1:]):
            ok += 1
    return ok / total if total else 0.0


def main() -> int:
    rom = ROM.read_bytes()
    print(f"ROM {len(rom):,} B   扫描 0x{LO:06X}..0x{HI:06X}\n")

    hits = []
    for stride in range(4, 17):
        for base in range(LO, HI - stride * N_CHECK, 1):
            r = compliance(rom, base, stride, N_CHECK)
            if r >= 0.98:
                hits.append((base, stride, r))

    print(f"合规率 ≥98% 的 (base, stride) 组合：{len(hits)} 个")
    # 合并相邻（同一张表会因为起点微移都合规）
    merged = []
    for base, stride, r in hits:
        if merged and base - merged[-1][0] < stride and stride == merged[-1][1]:
            merged[-1] = (merged[-1][0], stride, r)
        else:
            merged.append((base, stride, r))

    for base, stride, r in merged[:30]:
        print(f"\n  base=0x{base:06X}  stride={stride}  合规 {r:.0%}")
        for i in range(6):
            off = base + i * stride
            seg = rom[off:off + stride]
            print(f"    项{i} 0x{off:06X}: {seg.hex(' ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
