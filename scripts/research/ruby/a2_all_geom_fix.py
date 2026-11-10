#!/usr/bin/env python3
"""修正：可用宽度应取「元数据起点的众数」而不是最小值。

上一脚本错误：
  道具名报「元数据起 5」，是因为有个别条目名字只有 4 字 + 结尾，
  名字后紧跟非零元数据，于是 min(starts)=5。
  但 385/386 项的名字都补 0x00 到某个固定边界 —— 那才是真实可用宽度。

正确判据：元数据起点的**分布众数**（或「名字+填充」到边界的固定位置）。

另外必须区分两种表：
  定长补 0x00 型：名字后补 0 到边界，元数据从固定偏移开始
  变长 FF 分隔型：名字用 FF 结尾，紧接下一个字段

用法：
    python scripts/research/ruby/a2_all_geom_fix.py
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
sys.path.insert(0, str(ROOT / "src"))

BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
GBA_BASE = 0x08000000

TABLES = [
    ("招式名",         0x1CACFC, 8,  354),
    ("特性名",         0x1CBC44, 8,  77),
    ("属性名",         0x1CBB0C, 5,  18),
    ("道具名",         0x39A648, 40, 348),
    ("图鉴分类名",     0x38474C, 28, 386),
    ("秘密基地装饰名", 0x3C2A44, 28, 120),
]


def main() -> int:
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path
    from meowth.table_expand import encode_body

    cm = Charmap(charmap_path=get_charmap_path("POKEMON_RUBY_AXVJ00"),
                 target_lang="zh-Hans")
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    by_mod: dict[str, list] = {}
    for e in d.get("entries") or []:
        by_mod.setdefault(e.get("module") or "", []).append(e)

    print(f"{'表':<16} {'stride':>6} {'元数据众数':>10} {'出现率':>7} "
          f"{'结尾':>5} {'可用':>5} {'条数':>5} {'最长':>5} {'塞得下':>6}")
    print("-" * 88)

    for name, base, stride, n in TABLES:
        items = []
        for e in by_mod.get(name) or []:
            if e.get("type") != "replace" or e.get("phrase_code") is None:
                continue
            try:
                a = int(str(e.get("address") or "0x0").replace("0x", ""), 16)
            except ValueError:
                continue
            if a >= GBA_BASE:
                a -= GBA_BASE
            items.append((a, e))
        if not items:
            print(f"{name:<16}  无 F980 条目")
            continue

        starts = Counter()
        terms = Counter()
        for a, e in items:
            try:
                raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
            except ValueError:
                continue
            seg = rom[a:a + stride]
            p = len(raw)
            if 0 < p <= len(seg):
                terms[seg[p - 1]] += 1
            while p < len(seg) and seg[p] == 0x00:
                p += 1
            starts[p] += 1

        mode_start, mode_cnt = starts.most_common(1)[0]
        rate = mode_cnt / sum(starts.values())
        term = terms.most_common(1)[0][0]
        usable = mode_start

        bodies = [encode_body(cm, e.get("translated") or "")
                  for _, e in items if (e.get("translated") or "")]
        if not bodies:
            print(f"{name:<16}  无译文")
            continue
        fit = sum(1 for b in bodies if len(b) <= usable)
        longest = max(len(b) for b in bodies)

        print(f"{name:<16} {stride:>6} {mode_start:>10} {rate:>6.0%} "
              f"{f'0x{term:02X}':>5} {usable:>5} {len(bodies):>5} "
              f"{longest:>5} {fit:>6}")

    print()
    print("=== 说明 ===")
    print("  元数据众数 = 名字区结束的位置（多数条目一致）")
    print("  可用 = 元数据众数（名字实际能用的字节数）")
    print("  塞得下 = 译文编码长度 <= 可用的条数")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
