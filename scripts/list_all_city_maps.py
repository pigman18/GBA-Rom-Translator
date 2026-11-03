#!/usr/bin/env python3
"""按美版 map_groups + 日版实测校准，列出**所有城市**的室内地图 ID。

── 校准依据（已实证，见 scripts/map_ids_full.py）──────────────────────
  group 0  : Route118=33, Route119=34, MauvilleCity=2      ✓ 与美版一致
  group 2  : OldaleTown_PokemonCenter_1F=2                 ✓
  group 10 : MauvilleCity_Mart=7（美版第 8 项）             ✓
  group 3  : DewfordTown_Gym=3（本次新增验证：warp 命中且截图确认道馆）
  group 13 : LilycoveCity_ContestHall=5（本次验证：warp 命中，采到 92 帧）
  group 5  : FallarborTown_ContestLobby=1（验证：warp 命中，采到 59 帧）

⇒ 至少 group 0/2/3/5/10/13 与美版顺序完全一致，其余组按同规则换算。

用法：python scripts/list_all_city_maps.py
"""
from __future__ import annotations

# 每个城市组：组号 -> (城市名, [该组内各建筑名，顺序即下标])
CITIES = {
    2:  ("Oldale", ["House1", "House2", "PokemonCenter_1F", "PokemonCenter_2F", "Mart"]),
    3:  ("Dewford", ["House1", "PokemonCenter_1F", "PokemonCenter_2F", "Gym",
                     "Hall", "House2"]),
    4:  ("Lavaridge", ["HerbShop", "Gym_1F", "Gym_B1F", "House", "Mart",
                       "PokemonCenter_1F", "PokemonCenter_2F"]),
    5:  ("Fallarbor", ["Mart", "ContestLobby", "ContestHall", "PokemonCenter_1F",
                       "PokemonCenter_2F", "House1", "House2"]),
    6:  ("Verdanturf", ["ContestLobby", "ContestHall", "Mart", "PokemonCenter_1F",
                        "PokemonCenter_2F", "WandasHouse",
                        "FriendshipRatersHouse", "House"]),
    7:  ("Pacifidlog", ["PokemonCenter_1F", "PokemonCenter_2F", "House1", "House2",
                        "House3", "House4", "House5"]),
    8:  ("Petalburg", ["WallysHouse", "Gym", "House1", "House2",
                       "PokemonCenter_1F", "PokemonCenter_2F", "Mart"]),
    9:  ("Slateport", ["SternsShipyard_1F", "SternsShipyard_2F", "ContestLobby",
                       "ContestHall", "House1", "PokemonFanClub",
                       "OceanicMuseum_1F", "OceanicMuseum_2F", "Harbor",
                       "House2", "PokemonCenter_1F", "PokemonCenter_2F", "Mart"]),
    10: ("Mauville", ["Gym", "BikeShop", "House1", "GameCorner", "House2",
                      "PokemonCenter_1F", "PokemonCenter_2F", "Mart"]),
    11: ("Rustboro", ["DevonCorp_1F", "DevonCorp_2F", "DevonCorp_3F", "Gym",
                      "PokemonSchool", "PokemonCenter_1F", "PokemonCenter_2F",
                      "Mart"]),
    12: ("Fortree", ["House1", "Gym", "PokemonCenter_1F", "PokemonCenter_2F",
                     "Mart", "House2", "House3", "House4", "House5",
                     "DecorationShop"]),
    13: ("Lilycove", ["CoveLilyMotel_1F", "CoveLilyMotel_2F",
                      "LilycoveMuseum_1F", "LilycoveMuseum_2F", "ContestLobby",
                      "ContestHall", "PokemonCenter_1F", "PokemonCenter_2F"]),
    14: ("Mossdeep", ["Gym", "House1", "House2", "PokemonCenter_1F",
                      "PokemonCenter_2F", "Mart"]),
    15: ("Sootopolis", ["Gym_1F", "Gym_B1F", "PokemonCenter_1F",
                        "PokemonCenter_2F", "Mart"]),
}

# 要采的目标类型（按建筑名关键词匹配）
WANT_KINDS = ("PokemonCenter_1F", "Mart", "Gym", "Gym_1F", "ContestHall",
              "ContestLobby", "GameCorner", "BikeShop", "HerbShop",
              "DepartmentStore", "PokemonFanClub", "OceanicMuseum_1F")


def kind_of(name: str) -> str | None:
    """把建筑名归到采集模式。"""
    if name == "PokemonCenter_1F":
        return "counter"
    if name == "Mart":
        return "counter"
    if name in ("Gym", "Gym_1F"):
        return "gym"
    if name in ("ContestHall", "ContestLobby"):
        return "interior"
    if name == "GameCorner":
        return "counter_left"
    if name in ("BikeShop", "HerbShop"):
        return "counter_left"
    if name in ("PokemonFanClub", "OceanicMuseum_1F"):
        return "interior"
    return None


def main() -> int:
    print("=== 所有城市室内地图 ID（日版，按美版顺序 + 实测校准）===\n")
    print(f"{'地图':<44} {'ID':<9} {'模式':<13}")
    print("-" * 70)
    rows = []
    for g in sorted(CITIES):
        city, names = CITIES[g]
        for n, name in enumerate(names):
            if not any(k in name for k in WANT_KINDS):
                continue
            mode = kind_of(name)
            if mode is None:
                continue
            full = f"{city}{name}" if not name.startswith(city) else name
            # 城市前缀：Gym/PC/Mart 要带城市名，避免重名
            label = full if ("PokemonCenter" in name or name in ("Mart", "Gym",
                                                                "Gym_1F")) else full
            print(f"{label:<44} {g}:{n:<7} {mode:<13}")
            rows.append((label, g, n, mode))

    print(f"\n合计 {len(rows)} 个候选场景")
    print("\n已跑通的（不必重复）：")
    print("  MauvilleGym 10:0 / MauvillePC 10:5 / MauvilleMart 10:7")
    print("  OldalePC 2:2 / OldaleMart 2:4")
    print("  SlateportPC 9:10 / SlateportMart 9:12 / SlateportContestHall 9:3")
    print("  DewfordGym 3:3 / RustboroGym 11:3 / LavaridgeGym_1F 4:1")
    print("  LilycoveContestHall 13:5 / FallarborContestLobby 5:1")
    print("  MauvilleGameCorner 10:3 / MauvilleBikeShop 10:1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
