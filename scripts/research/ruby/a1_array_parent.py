#!/usr/bin/env python3
"""A1 定案：NO_PTR 文本被「0f 00 <ptr32>」形态的脚本数组引用。

实测结构（连续观察）：
  0x145AE2: ... 02 0f 00 | fc de 14 08 | 09 04 68 2a ...
  0x145B21: ... 6c 02 0f 00 | 92 5d 14 08 | 09 02 02 13 ...
  0x145B79: ... 03 02 0f 00 | 44 5f 14 08 | 09 03 02 0f 00 | cd 5e 14 08 ...

模式：`?? ?? 0f 00 <ptr32>` 反复出现 → 这是「脚本数组」，
每个元素 = 4 字节头部 + 4 字节指针。

若如此，这些脚本数组本身应当被更大的指针/表引用。
本脚本验证：
  1. 确认 `0f 00 <ptr>` 模式的出现频率
  2. 找这些数组的「父引用」（数组起点被谁指）

用法：
    python scripts/research/ruby/a1_array_parent.py
"""
from __future__ import annotations

import json
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
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
GBA_BASE = 0x08000000


def main() -> int:
    rom = ROM_PATH.read_bytes()
    print(f"ROM {len(rom):,} B\n")

    # 1. 扫「0f 00 + 合法指针」模式
    pat = 0
    positions = []
    i = 0
    n = len(rom) - 6
    while i < n:
        if rom[i] == 0x0F and rom[i + 1] == 0x00:
            v = struct.unpack_from("<I", rom, i + 2)[0]
            if GBA_BASE <= v < 0x0A000000:
                pat += 1
                positions.append(i)
                i += 6
                continue
        i += 1

    print(f"=== 「0f 00 <ptr32>」模式 ===")
    print(f"  命中 {pat:,} 处")
    if positions:
        zone = Counter()
        for p in positions:
            if p < 0x100000:
                zone["代码段"] += 1
            elif p < 0x1C0000:
                zone["ROM 0x100000-0x1C0000"] += 1
            elif p < 0x400000:
                zone["表区"] += 1
            else:
                zone["高地址"] += 1
        for z, c in zone.most_common():
            print(f"    {z:<24} {c}")

    # 2. 找这些位置的间距分布（是不是等距表格）
    if len(positions) > 1:
        gaps = Counter()
        for a, b in zip(positions, positions[1:]):
            gaps[b - a] += 1
        print()
        print("=== 相邻「0f 00」间距分布（前 10）===")
        for g, c in gaps.most_common(10):
            print(f"    {g:>6} 字节: {c:>5}")

    # 3. 抽一个密集区看结构
    if positions:
        # 找最密集的 4KB 区
        bucket = Counter(p >> 12 for p in positions)
        top = bucket.most_common(1)[0]
        base = top[0] << 12
        print()
        print(f"=== 最密区 0x{base:06X}（{top[1]} 处）===")
        for r in range(0, 96, 16):
            print(f"  0x{base + r:06X}: {rom[base + r:base + r + 16].hex(' ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
