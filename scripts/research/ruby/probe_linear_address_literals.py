#!/usr/bin/env python3
"""查「零基址字面量」的三张表是否存在逐元素硬算地址。

背景（probe_table_base_literals.py 结果）：
  招式名(0x1CAD04) / 特性名(0x1CBC4C) / 秘密基地装饰名(0x3C2A54)
  这三张表在整个 ROM 里找不到「表基址」的 u32 字面量。

可能原因：
  A. 基址是逐元素算出来的（base + k*stride），每个元素一个常量 → 仍可逐元素 patch
  B. 基址来自另一张索引表（如 gMonFrontPicTable 式的指针数组）→ 整表搬走即可
  C. 基址由运行时计算（如 0x1CAD04 = 某个符号 + 偏移）→ 最难

本脚本查 A：扫每个元素地址是否作为字面量出现。

用法：
    python scripts/research/ruby/probe_linear_address_literals.py
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
BASE = 0x08000000

# (标签, 名称字段起始文件偏移, 步长, 元素数)
TARGETS = [
    ("招式名        0x1CAD04 stride=8  n=354", 0x1CAD04, 8, 354),
    ("特性名        0x1CBC4C stride=8  n=77",  0x1CBC4C, 8, 77),
    ("秘密基地装饰名 0x3C2A61 size=28   n=120", 0x3C2A61, 28, 120),
    ("图鉴分类名字段 0x38474C size=28   n=386", 0x38474C, 28, 386),
]


def main() -> int:
    rom = ROM.read_bytes()
    print(f"ROM {len(rom):,} B\n")

    for label, start, stride, n in TARGETS:
        print(f"=== {label} ===")
        hit_elems = 0
        total_refs = 0
        samples = []
        for k in range(n):
            cand = start + k * stride
            needle = struct.pack("<I", cand + BASE)
            cnt = rom.count(needle)
            if cnt:
                hit_elems += 1
                total_refs += cnt
                if len(samples) < 5:
                    samples.append((cand, cnt))

        if hit_elems == 0:
            print(f"  ❌ 0/{n} 个元素地址作为字面量出现 → 不是逐元素硬算")
        elif hit_elems == n:
            print(f"  ✅ {hit_elems}/{n} 个元素地址都有字面量 → 逐元素硬算，可逐元素 patch")
        else:
            print(f"  ⚠️  {hit_elems}/{n} 个元素有字面量（部分）")
        print(f"  引用总次数 {total_refs}")
        for cand, cnt in samples:
            print(f"     0x{cand:06X} × {cnt}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
