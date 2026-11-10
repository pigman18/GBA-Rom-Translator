#!/usr/bin/env python3
"""texts_19: 内容重复的「真冗余」判定 —— 区分两种完全不同的情况。

重要区分（上一轮统计 1271 条冗余，但大部分不能删）：
  N1 同模块内的重复：同一个名字表里重复出现的名字（如「したっぱ」×54、
     「たね」×N），是**真实的不同表项**，删了会丢表项 → 不可删。
  N2 跨模块的重复：同一段 ROM 字节（同地址）被两个模块都收录 →
    这才是真冗余。但 texts_18 已证明同字节无重复收录，
     所以这里的「跨模块同内容」是**不同地址、同文本**，需要按语义判断：
       - 若两个模块语义不同（如「ユウキ」既是训练家名又是个人名）→ 保留
       - 若两个模块语义重复（剧情 vs 补漏剧情）→ 可合并

本脚本给出精确分类，不预设可删。

用法: python scripts/research/ruby/texts_19_dupKinds.py
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


def main() -> int:
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    byhex: dict[str, list] = defaultdict(list)
    for e in d["entries"]:
        h = (e.get("original_hex") or "").replace(" ", "").lower()
        if h:
            byhex[h].append(e)

    groups = {h: v for h, v in byhex.items() if len(v) > 1}
    within = {h: v for h, v in groups.items() if len({x.get("module") for x in v}) == 1}
    cross = {h: v for h, v in groups.items() if len({x.get("module") for x in v}) > 1}

    print("=" * 112)
    print("内容重复分类")
    print("=" * 112)
    print(f"  重复组总数            : {len(groups):,}")
    print(f"  N1 同模块内重复（不可删）: {len(within):,} 组，"
          f"涉及 {sum(len(v) for v in within.values()):,} 条")
    print(f"  N2 跨模块重复（需语义判断）: {len(cross):,} 组，"
          f"涉及 {sum(len(v) for v in cross.values()):,} 条")

    print()
    print("=" * 112)
    print("N1 同模块内重复 TOP 15（这些是正常的不同表项，不能删）")
    print("=" * 112)
    for h, v in sorted(within.items(), key=lambda kv: -len(kv[1]))[:15]:
        print(f"  x{len(v):<3} [{v[0].get('module')}] "
              f"{(v[0].get('original') or '')[:40]!r}")

    print()
    print("=" * 112)
    print("N2 跨模块重复：按模块对统计")
    print("=" * 112)
    pair = Counter()
    for h, v in cross.items():
        ms = sorted({x.get("module") for x in v})
        for i in range(len(ms)):
            for j in range(i + 1, len(ms)):
                pair[(ms[i], ms[j])] += 1
    for (a, b), c in pair.most_common():
        print(f"  {a:<20} vs {b:<20} {c:>5} 组")

    print()
    print("=" * 112)
    print("N2 跨模块重复：剧情 vs 补漏剧情 的样本（这两模块职责重叠）")
    print("=" * 112)
    shown = 0
    for h, v in cross.items():
        ms = {x.get("module") for x in v}
        if ms == {"剧情", "补漏剧情"} and shown < 10:
            print(f"  {(v[0].get('original') or '')[:60]!r}")
            for x in v:
                print(f"      0x{x.get('address')} [{x.get('module')}]")
            shown += 1

    print()
    print("=" * 112)
    print("N2 跨模块重复：UI界面 / 剧情 / 补漏剧情 三方重叠")
    print("=" * 112)
    tri = 0
    for h, v in cross.items():
        ms = {x.get("module") for x in v}
        if len(ms & {"UI界面", "剧情", "补漏剧情"}) >= 2:
            tri += 1
    print(f"  扫描类模块之间的同文本重复组: {tri}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
