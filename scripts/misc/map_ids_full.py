#!/usr/bin/env python3
"""按美版 map_groups.json + 日版实测校准，列出「窗口覆盖」需要的全部地图 ID。

── 校准依据（日版实测点，来自 prove 的 [POS] 与 savlib 解析）──────────
  0:2   MouvilleCity（美版 TownsAndRoutes 下标 2 ✓）
  0:33  Route118     （美版下标 33 ✓）
  0:34  Route119     （美版下标 34 ✓）
  2:2   OldaleTown_PokemonCenter_1F（美版 IndoorOldale 第 3 项=下标 2 ✓）
  10:7  MauvilleCity_Mart（美版 IndoorMauville 第 8 项=下标 7 ✓）
  ⇒ group 0 / 2 / 10 与美版顺序**完全一致**，故其余组按美版换算。

用法：python scripts/map_ids_full.py
"""
from __future__ import annotations

# 美版 map_groups.json 的相关组（顺序即下标）
GROUPS = {
    0: ["PetalburgCity", "SlateportCity", "MauvilleCity", "RustboroCity",
        "FortreeCity", "LilycoveCity", "MossdeepCity", "SootopolisCity",
        "EverGrandeCity", "LittlerootTown", "OldaleTown", "DewfordTown",
        "LavaridgeTown", "FallarborTown", "VerdanturfTown", "PacifidlogTown",
        "Route101", "Route102", "Route103", "Route104", "Route105", "Route106",
        "Route107", "Route108", "Route109", "Route110", "Route111", "Route112",
        "Route113", "Route114", "Route115", "Route116", "Route117", "Route118",
        "Route119", "Route120", "Route121", "Route122", "Route123", "Route124",
        "Route125", "Route126", "Route127", "Route128", "Route129", "Route130",
        "Route131", "Route132", "Route133", "Route134", "Underwater1",
        "Underwater2", "Underwater3", "Underwater4"],
    2: ["OldaleTown_House1", "OldaleTown_House2",
        "OldaleTown_PokemonCenter_1F", "OldaleTown_PokemonCenter_2F",
        "OldaleTown_Mart"],
    3: ["DewfordTown_House1", "DewfordTown_PokemonCenter_1F",
        "DewfordTown_PokemonCenter_2F", "DewfordTown_Gym",
        "DewfordTown_Hall", "DewfordTown_House2"],
    4: ["LavaridgeTown_HerbShop", "LavaridgeTown_Gym_1F",
        "LavaridgeTown_Gym_B1F", "LavaridgeTown_House",
        "LavaridgeTown_Mart", "LavaridgeTown_PokemonCenter_1F",
        "LavaridgeTown_PokemonCenter_2F"],
    5: ["FallarborTown_Mart", "FallarborTown_ContestLobby",
        "FallarborTown_ContestHall", "FallarborTown_PokemonCenter_1F",
        "FallarborTown_PokemonCenter_2F", "FallarborTown_House1",
        "FallarborTown_House2"],
    9: ["SlateportCity_SternsShipyard_1F", "SlateportCity_SternsShipyard_2F",
        "SlateportCity_ContestLobby", "SlateportCity_ContestHall",
        "SlateportCity_House1", "SlateportCity_PokemonFanClub",
        "SlateportCity_OceanicMuseum_1F", "SlateportCity_OceanicMuseum_2F",
        "SlateportCity_Harbor", "SlateportCity_House2",
        "SlateportCity_PokemonCenter_1F", "SlateportCity_PokemonCenter_2F",
        "SlateportCity_Mart"],
    10: ["MauvilleCity_Gym", "MauvilleCity_BikeShop", "MauvilleCity_House1",
         "MauvilleCity_GameCorner", "MauvilleCity_House2",
         "MauvilleCity_PokemonCenter_1F", "MauvilleCity_PokemonCenter_2F",
         "MauvilleCity_Mart"],
    11: ["RustboroCity_DevonCorp_1F", "RustboroCity_DevonCorp_2F",
         "RustboroCity_DevonCorp_3F", "RustboroCity_Gym",
         "RustboroCity_PokemonSchool", "RustboroCity_PokemonCenter_1F",
         "RustboroCity_PokemonCenter_2F", "RustboroCity_Mart"],
    13: ["LilycoveCity_CoveLilyMotel_1F", "LilycoveCity_CoveLilyMotel_2F",
         "LilycoveCity_LilycoveMuseum_1F", "LilycoveCity_LilycoveMuseum_2F",
         "LilycoveCity_ContestLobby", "LilycoveCity_ContestHall",
         "LilycoveCity_PokemonCenter_1F", "LilycoveCity_PokemonCenter_2F"],
}

# 要在场景里采的目标（名字 -> 组/索引）
WANT = [
    # 道馆（多城）
    ("DewfordTown_Gym", 3, 3),
    ("MauvilleCity_Gym", 10, 0),
    ("RustboroCity_Gym", 11, 3),
    ("LavaridgeTown_Gym_1F", 4, 1),
    # 宝可梦中心（治疗/PC/电脑）
    ("MauvilleCity_PokemonCenter_1F", 10, 5),
    ("OldaleTown_PokemonCenter_1F", 2, 2),
    ("SlateportCity_PokemonCenter_1F", 9, 10),
    # 商店（买卖）
    ("OldaleTown_Mart", 2, 4),
    ("SlateportCity_Mart", 9, 12),
    # 华丽大赛
    ("FallarborTown_ContestLobby", 5, 1),
    ("FallarborTown_ContestHall", 5, 2),
    ("SlateportCity_ContestHall", 9, 3),
    ("LilycoveCity_ContestHall", 13, 5),
    # 其他有文本的室内
    ("MauvilleCity_GameCorner", 10, 3),
    ("MauvilleCity_BikeShop", 10, 1),
]


def resolve(name: str, g: int, n: int) -> str:
    grp = GROUPS.get(g)
    if grp and n < len(grp):
        real = grp[n]
        mark = "✓" if real == name else f"⚠ 实为 {real}"
        return f"{g}:{n}  {mark}"
    return f"{g}:{n}  ⚠ 组 {g} 未收录"


def main() -> int:
    print("=== 目标地图 ID（日版，按美版顺序 + 实测校准换算）===\n")
    print(f"{'地图':<34} {'ID':<10} 校验")
    print("-" * 68)
    for name, g, n in WANT:
        print(f"{name:<34} {resolve(name, g, n)}")

    print("\n=== 与已跑通场景对照 ===")
    print("  MauvilleCity_Gym        10:0   ✅ 已跑通（gym_mauville）")
    print("  FallarborTown_ContestLobby 5:1 ✅ 已跑通（contest_hall）")
    print("\n=== 注意 ===")
    print("  · 落点 x/y 需要落在**地图内可走区域**，否则会落在黑屏里")
    print("    （华丽大赛 Lobby 用 (10,10) 就是黑屏，改 (8,5) 才对）")
    print("  · 一个场景只做一次 warp；连续第二次会 TIMEOUT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
