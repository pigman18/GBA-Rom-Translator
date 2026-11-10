#!/usr/bin/env python3
"""查：流水线报「119 条未放置」是什么。

现象：
  秘密基地装饰名 120 条进了流水线，但 119 条 placed_offset = 0。

怀疑：
  该表 base=0x3C2A44，但 build.json 条目地址可能不是 base + i*28 的形态。
  之前 TextsCurator 报告该表 name_offset=13，说明名字在项内偏移 13，
  所以条目地址 = base + i*28 + 13，不是 base + i*28！

_ index_in_table 只按 base + i*stride 匹配，没考虑 name_offset。

用法：
    python scripts/research/ruby/a2_check_unplaced.py
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
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
GBA_BASE = 0x08000000
RESULT = ROOT / "work" / "_probe" / "a2_pipeline_result.json"


def main() -> int:
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    res = json.loads(RESULT.read_text(encoding="utf-8"))

    # 找出未放置的条目来源
    by_module = Counter()
    for e in d.get("entries") or []:
        if e.get("type") != "replace" or e.get("phrase_code") is None:
            continue
        by_module[e.get("module")] += 1

    print("=== build.json 各模块 F980 条数 ===")
    for m, c in by_module.most_common():
        print(f"  {m:<18} {c}")

    print()
    print("=== 秘密基地装饰名 条目地址分析 ===")
    items = []
    for e in d.get("entries") or []:
        if e.get("module") != "秘密基地装饰名":
            continue
        if e.get("type") != "replace" or e.get("phrase_code") is None:
            continue
        try:
            a = int(str(e.get("address") or "0x0").replace("0x", ""), 16)
        except ValueError:
            continue
        if a >= GBA_BASE:
            a -= GBA_BASE
        items.append((a, e))
    items.sort()

    print(f"  条目 {len(items)} 条")
    BASE = 0x3C2A44
    STRIDE = 28
    print(f"  表基址 0x{BASE:06X} stride {STRIDE}")
    print(f"  前 6 条地址与 (addr - BASE) % STRIDE:")
    for a, e in items[:6]:
        delta = a - BASE
        print(f"    0x{a:06X}  Δ={delta:>6}  Δ%28={delta % 28:>3}  "
              f"{e.get('original')!r}")

    # 统计 Δ%stride 分布
    mods = Counter((a - BASE) % STRIDE for a, _ in items)
    print()
    print("  Δ % stride 分布:")
    for m, c in sorted(mods.items()):
        print(f"    {m}: {c}")

    print()
    print("=== 结论 ===")
    main_mod = mods.most_common(1)[0][0]
    if main_mod != 0:
        print(f"  ❌ 条目地址相对表基址偏移恒为 +{main_mod}")
        print(f"     ⇒ name_offset = {main_mod}，_index_in_table 必须减掉它")
        print(f"     ⇒ 表基址应写作 0x{BASE:06X}，名字在 +{main_mod}")
    else:
        print("  ✅ 偏移为 0，问题在别处")

    # 其他表对照
    print()
    print("=== 其他 5 张表的 Δ%stride ===")
    for name, base, stride in (
        ("招式名", 0x1CACFC, 8),
        ("特性名", 0x1CBC44, 8),
        ("属性名", 0x1CBB0C, 5),
        ("道具名", 0x39A648, 40),
        ("图鉴分类名", 0x38474C, 28),
    ):
        ms = Counter()
        for e in d.get("entries") or []:
            if e.get("module") != name:
                continue
            if e.get("type") != "replace" or e.get("phrase_code") is None:
                continue
            try:
                a = int(str(e.get("address") or "0x0").replace("0x", ""), 16)
            except ValueError:
                continue
            if a >= GBA_BASE:
                a -= GBA_BASE
            ms[(a - base) % stride] += 1
        top = ms.most_common(3)
        print(f"  {name:<16} " + ", ".join(f"Δ%{stride}={m}({c})"
                                           for m, c in top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
