#!/usr/bin/env python3
"""定位 gWildMonHeaders 里 Route118 的表项，并验证「改遇敌率能否让遇敌变确定」。

── 为什么要改遇敌率而不是别的 ────────────────────────────────────────────
实测这些手段都无效或不够：
  · gWildEncountersDisabled / sWildEncounterImmunitySteps —— 游戏运行时覆盖，写了没用
  · 只钉 gRngValue —— 两侧走位能逐格一致，但遇敌仍差一格（进格帧号不同）
最直接的办法：把目标地图的**遇敌率改成 100%**，这样每一步都必遇敌，
两侧在同一格必然同时触发，对照就成立了。

── gWildMonHeaders 结构（pokeruby）────────────────────────────────────
每个 map 一个 entry，按 mapGroup:mapNum 排列：
    struct WildPokemonHeader {
        u8 mapGroup, mapNum;            // +0,+1
        u8 landMonsInfo;                // +2  索引到 gWildMonInfo 表，0xFF = 无
        u8 waterMonsInfo;               // +3
        u8 rockSmashMonsInfo;           // +4
        u8 fishingMonsInfo;             // +5
        ... (其余字段版本相关)
    }
真正决定"遇敌率"的是 gWildMonInfo[landMonsInfo].encounterRate（u8）。

本脚本只做一件事：把 ROM 里 gWildMonHeaders 的每个表项打印出来，
按 mapGroup:mapNum 找到 Route118（0:33），再顺着 landMonsInfo 找到
gWildMonInfo 里的 encounterRate 字段偏移。

用法：python scripts/scan_wild_headers.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BASE = 0x08000000

G_WILD_MON_HEADERS = 0x0839D454
SIZE = 0x7A8          # 符号表给的长度

# pokemon ruby (JP) 的地图组：0:33 = Route118（本项目已实证）
TARGET = (0, 33)


def main() -> int:
    rom = ROM.read_bytes()
    off = G_WILD_MON_HEADERS - BASE
    blob = rom[off:off + SIZE]
    print(f"gWildMonHeaders @ 0x{G_WILD_MON_HEADERS:08X}  {SIZE}B")

    # 表按 8 字节步长扫：找 mapGroup/mapNum 都合理的项
    print("\n候选表项（按 mapGroup:mapNum 升序的心智模型逐步扫描）：")
    step = 8
    found_target = None
    for i in range(0, SIZE - step, step):
        g, n = blob[i], blob[i + 1]
        if g > 40 or n > 200:
            continue
        land, water, rock, fish = blob[i + 2], blob[i + 3], blob[i + 4], blob[i + 5]
        if land > 30 and land != 0xFF:
            continue
        if i < 40 or (g, n) == TARGET:
            print(f"  +0x{i:03X} {g}:{n} land=0x{land:02X} water=0x{water:02X} "
                  f"rock=0x{rock:02X} fish=0x{fish:02X}")
        if (g, n) == TARGET:
            found_target = i

    if found_target is None:
        print(f"\n[!] 没在 8 字节步长里找到 {TARGET[0]}:{TARGET[1]}，"
              "说明表项步长不是 8（可能是 12 或带指针）")
        # 退一步：整块里搜 mapGroup=0,mapNum=33 的字节对
        pat = bytes([TARGET[0], TARGET[1]])
        hits = [j for j in range(len(blob) - 1) if blob[j:j + 2] == pat]
        print(f"    字节对 00 21 出现在 +{[hex(h) for h in hits]}")
    else:
        print(f"\n★ Route118 = {TARGET[0]}:{TARGET[1]} 表项位于 +0x{found_target:03X} "
              f"(ROM 0x{G_WILD_MON_HEADERS + found_target:08X})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
