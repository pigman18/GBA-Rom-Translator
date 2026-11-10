#!/usr/bin/env python3
"""texts_26: 第4步前置 —— 摸清三个全 ROM scan 模块的真实地址分布。

要回答的问题（决定怎么划区间）：
  Q1 三模块的条目在 ROM 上的分布是什么样的？有无自然边界？
  Q2 剧情 vs 补漏剧情 是否存在真实的区域分工（还是纯粹靠 filter 抢）？
  Q3 0x3B2xxx 词库区、0x3E9xxx 资源区、0x1E04xx 资源区 各有多少条、归属谁？
  Q4 按 64KB 分箱统计，哪些箱只属于一个模块（可切区间）？

用法: python scripts/research/ruby/texts_26_scan_dist.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"


def to_int(v):
    if v is None:
        return None
    if isinstance(v, int):
        return v
    s = str(v).strip()
    try:
        return int(s, 16) if s.lower().startswith("0x") else int(s, 10)
    except ValueError:
        return None


def main() -> int:
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    scans = ["UI界面", "剧情", "补漏剧情"]
    by_mod: dict[str, list[int]] = defaultdict(list)
    for e in d["entries"]:
        mid = e.get("module")
        if mid not in scans:
            continue
        a = to_int(e.get("address"))
        if a is None:
            continue
        by_mod[mid].append(a - 0x08000000 if a >= 0x08000000 else a)

    print("=" * 112)
    print("Q1 三模块按 64KB 分箱分布")
    print("=" * 112)
    bins = range(0, 0x800000, 0x10000)
    print(f"  {'bin':>10} {'UI界面':>8} {'剧情':>8} {'补漏剧情':>9}   独占")
    print("  " + "-" * 55)
    for b in bins:
        c = {m: sum(1 for a in by_mod[m] if b <= a < b + 0x10000) for m in scans}
        if not any(c.values()):
            continue
        owners = [m for m in scans if c[m] > 0]
        tag = owners[0] if len(owners) == 1 else f"共享({len(owners)})"
        print(f"  0x{b:06X} {c['UI界面']:>8} {c['剧情']:>8} {c['补漏剧情']:>9}   {tag}")

    print()
    print("=" * 112)
    print("Q2/Q3 关键区段的模块归属")
    print("=" * 112)
    zones = [
        ("脚本低区 0x100000-0x1C4000", 0x100000, 0x1C4000),
        ("名表簇 0x1C4000-0x1D0000", 0x1C4000, 0x1D0000),
        ("资源区 0x1E0000-0x200000", 0x1E0000, 0x200000),
        ("图鉴区 0x37D000-0x388000", 0x37D000, 0x388000),
        ("招式说明区 0x392000-0x397500", 0x392000, 0x397500),
        ("道具区 0x398000-0x39E000", 0x398000, 0x39E000),
        ("树果/饰名区 0x3A1000-0x3C4000", 0x3A1000, 0x3C4000),
        ("词库区 0x3B2000-0x3B2A00", 0x3B2000, 0x3B2A00),
        ("UI字库 0x3DC000-0x3EAFFF", 0x3DC000, 0x3EAFFF),
        ("高位 0x700000-0x800000", 0x700000, 0x800000),
    ]
    print(f"  {'区段':<32} {'UI界面':>8} {'剧情':>8} {'补漏剧情':>9}")
    print("  " + "-" * 62)
    for label, lo, hi in zones:
        c = {m: sum(1 for a in by_mod[m] if lo <= a <= hi) for m in scans}
        print(f"  {label:<32} {c['UI界面']:>8} {c['剧情']:>8} {c['补漏剧情']:>9}")

    print()
    print("=" * 112)
    print("Q4 三模块的真实边界（最小/最大地址）")
    print("=" * 112)
    for m in scans:
        a = sorted(by_mod[m])
        if not a:
            continue
        print(f"  {m:<10} n={len(a):>5}  0x{a[0]:06X} .. 0x{a[-1]:06X}")

    print()
    print("=" * 112)
    print("Q5 剧情 vs 补漏剧情：地址是否交错（交错则无天然区间分工）")
    print("=" * 112)
    st = set(by_mod["剧情"])
    bl = set(by_mod["补漏剧情"])
    both_bins = Counter()
    for a in bl:
        if any((a + k) in st for k in (-8, -4, 0, 4, 8)):
            both_bins[a >> 16] += 1
    print(f"  补漏剧情条目中，±8 字节内就有剧情条目的: {sum(both_bins.values())} / {len(bl)}")
    print(f"  分布在前 8 个 bin: {both_bins.most_common(8)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
