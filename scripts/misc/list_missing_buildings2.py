#!/usr/bin/env python3
"""精确列出未铺建筑：直接从 bot/scenes 里的 .lua 文件解析出用到的 map id。

── 为什么不用 SCENE_DEFS ──────────────────────────────────────────────
SCENE_DEFS 里有些是手工场景（文件实际内容不来自模板），
还有一些 map id 写成不同格式。直接扫**场景文件里 api.warp 的 map 值**
最准确 —— 那是运行时真正用的。

用法：python scripts/list_missing_buildings2.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from list_all_city_maps import CITIES  # noqa: E402

SCENES = ROOT / "bot" / "scenes" / "POKEMON_RUBY_AXVJ00"


def used_map_ids() -> dict[str, str]:
    """返回 {mapId: 场景名}，从所有场景文件的 api.warp{map=...} 里抓。"""
    out = {}
    for f in SCENES.glob("*.lua"):
        txt = f.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'api\.warp\s*\{\s*map\s*=\s*"([\d:\-]+)"', txt):
            out.setdefault(m.group(1), f.stem)
    return out


def main() -> int:
    used = used_map_ids()
    print(f"场景文件里出现的 map id：{len(used)} 个\n")

    total = 0
    missing: list[tuple[str, str]] = []
    for grp in sorted(CITIES):
        city, names = CITIES[grp]
        for n, bname in enumerate(names):
            total += 1
            mid = f"{grp}:{n}"
            if mid in used:
                continue
            missing.append((mid, f"{city}{bname}"))

    by_group: dict[int, list[tuple[str, str]]] = {}
    for mid, label in missing:
        g = int(mid.split(":")[0])
        by_group.setdefault(g, []).append((mid, label))

    for g in sorted(by_group):
        city, _ = CITIES[g]
        print(f"--- group {g} ({city}) ---")
        for mid, label in by_group[g]:
            print(f"  {mid:<8} {label}")

    print(f"\n建筑总数 {total}，已铺 {total - len(missing)}，"
          f"**未铺 {len(missing)}**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
