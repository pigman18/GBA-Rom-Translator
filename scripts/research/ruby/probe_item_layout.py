#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""道具表布局实测：名字区、填充、各字段真实字节。

用途：决定「把名字搬到指针」时，entry 内哪一段可以安全改写。
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
BASE = 0x39A648
STRIDE = 40
N = 348


def main() -> int:
    rom = ROM.read_bytes()
    print(f"真ROM {ROM.name}  道具表 base=0x{BASE:06X} stride={STRIDE} n={N}\n")

    print("列说明：每个 entry 前 16 字节（名字区 + 填充 + u16 字段）")
    print(f"{'i':>4} {'0..8 (名字+EOS)':<28}{'+9..+0xF':<18}{'+0x10 起'}")
    print("-" * 96)
    for i in list(range(0, 4)) + [9, 10, 100, 200, 347]:
        e = BASE + i * STRIDE
        name = rom[e:e + 9]
        pad = rom[e + 9:e + 0x10]
        rest = rom[e + 0x10:e + 0x18]
        print(f"{i:>4} {name.hex(' '):<28}{pad.hex(' '):<18}{rest.hex(' ')}")

    print()
    # 统计 +9..+0xF 这 7 字节的内容规律
    from collections import Counter
    pad_vals = Counter()
    for i in range(N):
        e = BASE + i * STRIDE
        pad_vals[bytes(rom[e + 9:e + 0x10])] += 1
    print("+9..+0xF（7 字节）取值分布 top5：")
    for v, c in pad_vals.most_common(5):
        print(f"   {v.hex(' ')}  ×{c}")

    # 名字实际长度（到 FF）
    lens = Counter()
    for i in range(N):
        e = BASE + i * STRIDE
        seg = rom[e:e + 9]
        k = seg.find(b"\xff")
        lens[k if k >= 0 else 9] += 1
    print()
    print("原版名字长度分布（不含 FF）：")
    for k in sorted(lens):
        print(f"   {k}B: {lens[k]}")

    # +0x10 指针指向哪里
    import struct
    same_as_name = 0
    for i in range(N):
        e = BASE + i * STRIDE
        p = struct.unpack_from("<I", rom, e + 0x10)[0]
        if 0x08000000 <= p < 0x08400000:
            off = p - 0x08000000
            if e <= off < e + STRIDE:
                same_as_name += 1
    print()
    print(f"+0x10 指针指回本 entry 内部: {same_as_name}/{N}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
