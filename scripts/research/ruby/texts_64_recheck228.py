#!/usr/bin/env python3
"""texts_64: 独立核验 补漏剧情 剩余 228 条的真实分布（不采信转述，自己算）。

Chief 给出 7 类（A战斗台词64 / B人名84 / C音效19 / D词库15 / E单位9 / Fなし4 / G散点11）。
本脚本按地址段独立归类，与 Chief 的分类对照，重点查：
  Q1 各类的地址段是否真的如描述
  Q2 A 类 64 条是否真是「完整战斗台词」（还是碎片）
  Q3 B 类 84 条是否与人名/称呼相关，能否并进 训练家个人名
  Q4 C 类音效标签（ＢＧＭ/ＳＥ/ＰＡＮ/ＧＩＭ）在 ROM 里是否有显示路径

用法: python scripts/research/ruby/texts_64_recheck228.py
"""
from __future__ import annotations

import json
import re
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
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BASE = 0x08000000


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


ZONES = [
    ("A 0x3D0000-0x3E0000", 0x3D0000, 0x3E0000),
    ("B 0x3E9000-0x3EB000", 0x3E9000, 0x3EB000),
    ("C 0x3A5000-0x3A6000", 0x3A5000, 0x3A6000),
    ("D 0x3B2000-0x3B4000", 0x3B2000, 0x3B4000),
    ("E 0x1EC000-0x1ED000", 0x1EC000, 0x1ED000),
    ("F 0x185000-0x186000", 0x185000, 0x186000),
]


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    sup = [e for e in d["entries"] if e.get("module") == "补漏剧情"]
    print(f"补漏剧情实际条目: {len(sup)}\n")

    # 按区域归类
    buckets: dict[str, list] = defaultdict(list)
    for e in sup:
        off = to_int(e["address"]) - BASE
        placed = False
        for name, lo, hi in ZONES:
            if lo <= off < hi:
                buckets[name].append(e)
                placed = True
                break
        if not placed:
            buckets["G 其它"].append(e)

    print("=" * 112)
    print("按地址段归类（我的独立计算结果）")
    print("=" * 112)
    for name, els in sorted(buckets.items()):
        print(f"\n  {name}: {len(els)} 条")
        for e in els[:6]:
            print(f"      0x{to_int(e['address']):08X} {e['original'][:50]!r}")

    print()
    print("=" * 112)
    print("Q2 A 类（0x3D 区）是否「完整战斗台词」")
    print("=" * 112)
    a = buckets["A 0x3D0000-0x3E0000"]
    for e in a[:15]:
        t = e["original"]
        # 判定：有控制码 \XX + 有多段 + 有句子特征
        has_ctrl = bool(re.search(r"\\[0-9A-Fa-f]{2}", t))
        has_punct = any(c in t for c in "！？。")
        has_nl = "\n" in t
        print(f"  0x{to_int(e['address']):08X} ctrl={has_ctrl} punct={has_punct} "
              f"nl={has_nl} {t[:46]!r}")

    print()
    print("=" * 112)
    print("Q3 B 类（0x3E9 区）内容")
    print("=" * 112)
    b = buckets["B 0x3E9000-0x3EB000"]
    for e in b[:25]:
        print(f"  0x{to_int(e['address']):08X} {e['original']!r}")

    print()
    print("=" * 112)
    print("Q4 C 类（0x3A5 区）音效标签")
    print("=" * 112)
    c = buckets["C 0x3A5000-0x3A6000"]
    for e in c:
        print(f"  0x{to_int(e['address']):08X} {e['original']!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
