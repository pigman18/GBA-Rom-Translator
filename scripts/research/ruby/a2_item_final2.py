#!/usr/bin/env python3
"""道具名结构定案（第三次修正）。

反汇编铁证：
    0x0A5388: lsls r0,r1,#2 / adds r0,r0,r1 / lsls r0,r0,#3  = idx*40
    0x0A538E: ldr r1,[pc,#8] → 0x0839A648
    0x0A5390: adds r0,r0,r1                                  = 0x39A648 + idx*40

build.json 条目地址与 0x39A648 + i*40 + 0x28 完全吻合（6/6 抽样，281/348 全量）。

⇒ 结构是：每项 40 字节头，**名字从 +0x28 开始，但只有 0x18 = 24 字节**，
  因为 +0x28 到下一项起点（+0x28+?) 之间有 24 字节空间：
      0x39A648 + 0*40 = 0x39A648，+0x28 = 0x39A670
      0x39A648 + 1*40 = 0x39A670 ← 下一项起点就是 0x39A670！

等等，那 0x39A670 既是 item0 的 name，又是 item1 的 base？

重新算：
  item0 base = 0x39A648, name@+0x28 = 0x39A670
  item1 base = 0x39A670 ← 这正好是 item0 的名字位置！

说明我的 stride 算错了。让我重新推。
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
        if e.get("module") != "道具名":
            continue
        try:
            addr = int(str(e.get("address") or "").replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        items.append((addr, e))
    items.sort()
    addrs = [a for a, _ in items]

    print(f"道具名条目 {len(addrs)} 条，范围 0x{addrs[0]:06X}..0x{addrs[-1]:06X}\n")

    # 相邻间隔
    gaps = Counter(b - a for a, b in zip(addrs, addrs[1:]))
    print("=== 相邻名字地址间隔 ===")
    for g, c in gaps.most_common(8):
        print(f"  {g} 字节: {c}")

    # 若间隔是 40，则 stride=40
    main_gap = gaps.most_common(1)[0][0]
    print(f"\n  主导间隔 = {main_gap}")
    print(f"  ⇒ 名字字段本身以 {main_gap} 字节为步长")

    # 由此推：base = 第一个名字地址 - 0x28?
    first = addrs[0]
    print(f"\n=== 第一个名字 @0x{first:06X} ===")
    print(f"  0x39A648 + 0x28 = 0x{0x39A648 + 0x28:06X}"
          + ("  ✅ 吻合" if first == 0x39A648 + 0x28 else "  ❌"))

    # 关键：name 字段能有多长？到下一个名字的距离
    print()
    print("=== 名字字段可用宽度（到下一个名字的距离）===")
    widths = Counter()
    for a, b in zip(addrs, addrs[1:]):
        widths[b - a] += 1
    for w, c in widths.most_common(5):
        print(f"  {w} 字节: {c}")

    # 实测每个名字的实际长度
    print()
    print("=== 名字实际长度 vs 可用宽度 ===")
    over = 0
    for a, e in items[:10]:
        raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
        print(f"  0x{a:06X}  {len(raw)}B  {e.get('original')!r}")
    print()
    # 全量：原文最长多少
    lens = Counter()
    for a, e in items:
        try:
            raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
        except ValueError:
            continue
        lens[len(raw)] += 1
    print("  原文长度分布（前 8）:")
    for n, c in lens.most_common(8):
        print(f"    {n}B: {c}")
    print(f"  最长 {max(lens)}B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
