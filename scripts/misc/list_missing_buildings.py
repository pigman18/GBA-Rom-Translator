#!/usr/bin/env python3
"""列出还没铺场景的建筑（对比 CITIES 全表与 SCENE_DEFS 已用地图 ID）。

用法：python scripts/list_missing_buildings.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from list_all_city_maps import CITIES  # noqa: E402


def load_gen():
    gen = ROOT / "scripts" / "gen_scenes.py"
    spec = importlib.util.spec_from_file_location("gen", gen)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main() -> int:
    g = load_gen()
    used = {v[0] for v in g.SCENE_DEFS.values()}
    # 手工场景也要算进去（它们的 map id 不在 SCENE_DEFS 里，
    # 或者 SCENE_DEFS 里留的是记录值而实际文件是手写的）。
    MANUAL = {
        "gym_dewford": "3:3", "contest_lilycove": "13:5",
        "gym_mauville": "10:0", "contest_hall": "5:1",
        "battle_full": "0:33", "battle_dialog": "0:33",
        "battle_result": "0:33",
    }
    used |= set(MANUAL.values())

    total = 0
    missing = 0
    for grp in sorted(CITIES):
        city, names = CITIES[grp]
        rows = []
        for n, bname in enumerate(names):
            total += 1
            mid = f"{grp}:{n}"
            if mid in used:
                continue
            rows.append((mid, f"{city}{bname}"))
            missing += 1
        if rows:
            print(f"--- group {grp} ({city}) ---")
            for mid, label in rows:
                print(f"  {mid:<8} {label}")
    print(f"\n建筑总数 {total}，已铺 {total - missing}，**未铺 {missing}**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
