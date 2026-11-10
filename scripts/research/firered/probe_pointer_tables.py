#!/usr/bin/env python3
"""火红定长表是否「整表换变长指针表」？——实测指针数组。

用户指出：整表换变长本来就是允许的，缩写是没办法才用，否则不采用。

上一轮我误写「3 字以上要么缩写要么换变长」，需要实测澄清火红的真实做法。

做法：
  1. 火红汉化版里找出所有指向中文区（0x6D0000..0x730000 等）的 u32
  2. 聚类成「连续 4 字节排列」的数组
  3. 若某数组元素单调递增且指向 FF 结尾的中文串 → 就是「指针表」
  4. 对照原版同位置：原来是什么（日文定长表？还是同样有指针数组？）

用法：
    python scripts/research/firered/probe_pointer_tables.py
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
# 火红汉化新增文本区（多个）
ZH_REGIONS = [(0x6D0000, 0x730000), (0x71D000, 0x720000), (0xAF5000, 0xB00000)]


def in_zh_regions(t: int) -> bool:
    return any(lo <= t < hi for lo, hi in ZH_REGIONS)


def collect_ptrs(rom: bytes):
    """返回 [(来源偏移, 目标文件偏移)]，只收指向中文区的。"""
    out = []
    for off in range(0, len(rom) - 4, 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            t = v - GBA_BASE
            if in_zh_regions(t):
                out.append((off, t))
    return out


def cluster(ptrs):
    """把来源偏移连续（4 字节间隔）的聚成数组。"""
    arrays = []
    cur = []
    prev_off = None
    for off, tgt in ptrs:
        if prev_off is not None and off == prev_off + 4:
            cur.append((off, tgt))
        else:
            if len(cur) >= 8:
                arrays.append(cur)
            cur = [(off, tgt)]
        prev_off = off
    if len(cur) >= 8:
        arrays.append(cur)
    return arrays


def is_monotonic(arr) -> bool:
    tgts = [t for _, t in arr]
    return all(b >= a for a, b in zip(tgts, tgts[1:]))


def main() -> int:
    a = ORIG.read_bytes()
    b = ZH.read_bytes()
    print(f"origin / translated 各 {len(a):,} B\n")

    ptrs = collect_ptrs(b)
    print(f"指向中文区的指针 {len(ptrs):,} 个")
    arrays = cluster(ptrs)
    print(f"聚成 ≥8 元素的连续数组 {len(arrays)} 个\n")

    # 按「长度 × 单调性」排序，名字表特征：元素多、单调递增、跨度大
    scored = []
    for arr in arrays:
        tgts = [t for _, t in arr]
        spread = max(tgts) - min(tgts)
        mono = is_monotonic(arr)
        scored.append((len(arr), mono, spread, arr))
    scored.sort(key=lambda x: (-x[0], -x[2]))

    print("=== 最像「名字指针表」的数组（元素多 + 单调 + 跨度大）===")
    for n, mono, spread, arr in scored[:12]:
        start = arr[0][0]
        print(f"  数组 @ 0x{start:06X}  {n} 元素  单调={mono}  跨度 0x{spread:X}")
        for off, tgt in arr[:4]:
            seg = b[tgt:tgt + 20]
            ff = seg.find(b"\xFF")
            body = seg[:ff] if ff >= 0 else seg
            print(f"    0x{off:06X} → 0x{tgt:06X}  body={body.hex(' ')}  "
                  f"({len(body)}B, F7数={body.hex(' ').split().count('f7')})")
        # 原版同位置是什么
        orig_slice = a[start:start + 4 * min(n, 4)]
        print(f"    原版同位置: {orig_slice.hex(' ')}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
