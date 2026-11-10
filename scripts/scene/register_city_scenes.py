#!/usr/bin/env python3
"""把所有新城市场景注册进 scene_saves.json（默认用 Route118 存档）。

为什么统一用 Route118：这些场景都会先 roam 出门到城市再 warp，
起点在哪个野外都行；用 Route118 是因为它已实证可稳定读档 + 出门。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "bot" / "scenes" / "POKEMON_RUBY_AXVJ00" / "saves" / "scene_saves.json"

NEW = [
    "center_dewford", "herbshop_lavaridge", "mart_lavaridge", "center_lavaridge",
    "mart_fallarbor", "contest_fallarbor", "center_fallarbor",
    "contest_verdanturf_l", "contest_verdanturf", "mart_verdanturf",
    "center_verdanturf", "center_pacifidlog",
    "gym_petalburg", "center_petalburg", "mart_petalburg",
    "contest_slateport_l", "fanclub_slateport", "museum_slateport",
    "center_rustboro", "mart_rustboro",
    "gym_fortree", "center_fortree", "mart_fortree",
    "contest_lilycove_l", "center_lilycove",
    "gym_mossdeep", "center_mossdeep", "mart_mossdeep",
    "gym_sootopolis", "center_sootopolis", "mart_sootopolis",
]


def main() -> int:
    d = json.loads(P.read_text(encoding="utf-8"))
    n = 0
    for name in NEW:
        if name not in d["scenes"]:
            d["scenes"][name] = "Route118_68-7.sav"
            n += 1
    P.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 注册 {n} 个，共 {len(d['scenes'])} 个场景映射")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
