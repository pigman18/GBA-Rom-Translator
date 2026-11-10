#!/usr/bin/env python3
"""A1.4 突破：0x3B2810 前的 `xx 01` 序列是 u16 索引表！

观察 0x3B2810 往前 64 字节：
  85 01 | 40 00 | 69 01 | 1a 00 | 52 01 | 1d 01 | 51 01 | 97 01 | 98 01 | 45 01 ...

0x0185 = 389, 0x0140 = 320, 0x0169 = 361 ... 这些小值是 u16。
若它们是「相对某基址的偏移」，就能解释为什么搜不到 u32 指针。

验证：把每个零引用文本地址 A 换算成 u16 (A - base)，
看是否能在 ROM 里作为 u16 出现。

用法：
    python scripts/research/ruby/a1_u16_index.py
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
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
OWN = ROOT / "work" / "_probe" / "a1_ownership.json"
GBA_BASE = 0x08000000


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    by_addr = {}
    for e in d.get("entries") or []:
        a = e.get("address") or ""
        try:
            addr = int(str(a).replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        by_addr[addr] = e

    own = json.loads(OWN.read_text(encoding="utf-8"))
    targets = {int(r["addr"].replace("0x", ""), 16) for r in (own.get("NO_PTR") or [])}

    ref_targets: set[int] = set()
    for off in range(0, len(rom) - 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            ref_targets.add(v - GBA_BASE)

    zero = sorted(t for t in targets if t not in ref_targets and t > 0 and rom[t-1] == 0xFF)
    zone = [a for a in zero if 0x3B0000 <= a < 0x3C0000]
    print(f"0x3B 段零引用独立串: {len(zone):,}\n")

    # 检验各种基址下 u16 偏移命中率
    print("=== u16 偏移假设：A - base 是否作为 u16 出现 ===")
    best = None
    for base in (0x3B0000, 0x3B2000, 0x3B2400, 0x3B2800, 0x3A0000, 0x380000, 0x0):
        hit = 0
        for a in zone:
            off16 = a - base
            if 0 <= off16 < 0x10000:
                pat = struct.pack("<H", off16)
                # 只在 0x3B0000 前 0x3000 范围内找（索引表应在文本前面）
                lo = max(0, base - 0x4000)
                if rom.find(pat, lo, base + 0x100) >= 0:
                    hit += 1
        rate = hit / len(zone) if zone else 0
        print(f"  base 0x{base:06X}: 命中 {hit:>3}/{len(zone)} ({rate:.1%})")
        if best is None or rate > best[1]:
            best = (base, rate, hit)

    print()
    if best and best[1] > 0.5:
        base, rate, hit = best
        print(f"=== 最可能的基址 0x{base:06X}（{rate:.1%} 命中）===")
        # 精确定位索引表位置
        print("  定位索引表：逐个检查 A-base 的 u16 是否在 ROM 里成片出现")
        positions: Counter = Counter()
        for a in zone:
            off16 = a - base
            if 0 <= off16 < 0x10000:
                pat = struct.pack("<H", off16)
                s = rom.find(pat, max(0, base - 0x8000), base + 0x100)
                if s >= 0:
                    positions[s >> 8] += 1
        print("  索引值最集中的 256B 区段:")
        for seg, c in positions.most_common(6):
            print(f"    0x{seg << 8:06X}..0x{seg << 8 | 0xFF:06X}: {c} 个")
    else:
        print("=== u16 偏移假设不成立（命中率过低）===")
        print("  下一步应查：u16 相对于结构体起点的偏移，或完全不同的访问方式")

    # 无论如何，先看看 0x3B2810 前那段 0x01xx 序列到底是什么
    print()
    print("=== 0x3B27D0..0x3B2840 逐 u16 解析 ===")
    for off in range(0x3B27D0, 0x3B2840, 16):
        vals = struct.unpack_from("<8H", rom, off)
        print(f"  0x{off:06X}: " + " ".join(f"{v:5d}" for v in vals))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
