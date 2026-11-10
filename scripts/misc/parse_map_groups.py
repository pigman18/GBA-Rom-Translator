#!/usr/bin/env python3
"""把 Gen3 的地图组表解析出来，确认 map=0:2 这些编号对应哪张图。

为什么要这个：bot 日志现在打 `map=g:n`（如 `0:2`、`10:7`），
但只有编号不知道是哪个城市 —— 而覆盖道馆/大赛全靠"走到正确的城"。
savlib 里有一份美版地图表（tools/pokeruby/data/maps/map_groups.json），
本仓不存在该文件，所以改成**从 ROM 里读地图组表**。

── 依据 ────────────────────────────────────────────────────────────────
符号表（KEEP-US 可信）：
    gMapGroups           地图组指针数组
    gMapGroup_TownsAndRoutes 等
本脚本先打印符号表里所有 gMap* 的地址，再按指针解一层，
输出 (group, num) -> 地图名/宽高。

用法：python scripts/parse_map_groups.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
SYM = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "symbols" / "pokeruby_jp.sym"
BASE = 0x08000000


def load_syms():
    out = {}
    if not SYM.is_file():
        return out
    for line in SYM.read_text(encoding="utf-8", errors="replace").splitlines():
        p = line.split()
        if len(p) >= 2:
            try:
                addr = int(p[0], 16)
            except ValueError:
                continue
            out[p[1]] = addr
    return out


def u32(b, o):
    return int.from_bytes(b[o:o + 4], "little")


def main() -> int:
    syms = load_syms()
    maps = {k: v for k, v in syms.items() if k.startswith("gMap")}
    print(f"符号表里 gMap* 共 {len(maps)} 个：")
    for k in sorted(maps):
        print(f"  {k:<44} 0x{maps[k]:08X}")

    rom = ROM.read_bytes()

    # gMapGroups 是 u32[] 指向各组；先找它的地址
    grp = syms.get("gMapGroups")
    if grp is None:
        print("\n[!] 符号表没有 gMapGroups，无法直接解组表")
        # 退而求其次：打印所有 gMapGroup_* 的地址，供后续手工对照
        return 0

    off = grp - BASE
    print(f"\ngMapGroups @0x{grp:08X}")
    for gi in range(16):
        ptr = u32(rom, off + gi * 4)
        if not (0x08000000 <= ptr < 0x0A000000):
            break
        print(f"  group[{gi:2d}] -> 0x{ptr:08X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
