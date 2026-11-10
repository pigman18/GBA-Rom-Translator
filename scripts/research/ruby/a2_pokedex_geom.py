#!/usr/bin/env python3
"""从 ROM 反推图鉴分类名的真实几何（不信任 texts.json）。

已知 texts.json 说 base=0x38474C stride=28 name_offset=6，但：
  - build.json 条目地址与 BASE+i*28+6 吻合 0/20
  - ROM 里只有 44/386 项在 +6 处含 FF

所以几何是错的。用 build.json 的实际条目地址反推。

用法：
    python scripts/research/ruby/a2_pokedex_geom.py
"""
from __future__ import annotations

import json
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
GBA_BASE = 0x08000000


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    items = []
    for e in d.get("entries") or []:
        if e.get("module") != "图鉴分类名":
            continue
        try:
            a = int(str(e.get("address") or "0x0").replace("0x", ""), 16)
        except ValueError:
            continue
        if a >= GBA_BASE:
            a -= GBA_BASE
        items.append((a, e))
    items.sort()
    addrs = [a for a, _ in items]

    print(f"图鉴分类名条目 {len(addrs)} 条")
    print(f"地址范围 0x{addrs[0]:06X}..0x{addrs[-1]:06X}")
    print()

    # 相邻间隔
    gaps = Counter(b - a for a, b in zip(addrs, addrs[1:]))
    print("=== 相邻地址间隔（前 10）===")
    for g, c in gaps.most_common(10):
        print(f"  {g} 字节: {c}")

    main_gap = gaps.most_common(1)[0][0]
    print(f"\n  主导间隔 = {main_gap}")

    # 前 10 条详情
    print()
    print("=== 前 10 条 ===")
    for a, e in items[:10]:
        seg = rom[a:a + 24]
        ff = seg.find(b"\xFF")
        print(f"  0x{a:06X}  {(e.get('original') or '')[:20]!r}")
        print(f"    ROM: {seg.hex(' ')}  FF@{ff}")

    # 反推：找 base 和 name_offset
    # 假设 addrs[i] = base + i*stride + noff
    first = addrs[0]
    print()
    print("=== 反推 base / stride / name_offset ===")
    best = []
    for stride in range(8, 65):
        for noff in range(0, min(stride, 24)):
            base = first - noff
            if base < 0:
                continue
            ok = sum(1 for a in addrs
                     if a >= base and (a - base - noff) % stride == 0)
            rate = ok / len(addrs)
            if rate > 0.95:
                best.append((rate, stride, noff, base, ok))

    best.sort(reverse=True)
    for rate, stride, noff, base, ok in best[:10]:
        print(f"  base=0x{base:06X} stride={stride:>3} noff={noff:>3}  "
              f"{ok}/{len(addrs)} ({rate:.0%})")

    if not best:
        print("  ❌ 找不到合适的 (base, stride, noff)")
        print()
        print("  说明：条目地址不是「等距表」结构，可能是别的布局")
        # 看地址是否连续
        cont = sum(1 for a, b in zip(addrs, addrs[1:])
                   if b > a and b - a <= 40)
        print(f"  相邻地址差 <=40 的有 {cont}/{len(addrs)-1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
