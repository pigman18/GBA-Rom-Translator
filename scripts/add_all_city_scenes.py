#!/usr/bin/env python3
"""把所有城市室内地图加进 gen_scenes.py 的 SCENE_DEFS。

── 为什么可以批量加 ────────────────────────────────────────────────────
1. **地图 ID 有依据**：group 0/2/3/5/10/13 已用实测 warp 验证与美版一致，
   其余组按同规则换算（scripts/list_all_city_maps.py）。
2. **落点不用猜**：每个城市室内图的 NPC 位置都可以先 warp 进去采一帧，
   再用 scripts/list_interactables.py 解出。但为了先铺量，这里用
   「中心落点 + 四方向 talk 试探」的通用模板，采不到再单独校准。
3. **模式已有三种**：counter / counter_left / gym / interior。

⚠ 落点策略：
   · 商店/PC 通常柜台在正上方 → 落点取地图中心偏下，先 UP
   · 道馆布局各异 → gym 模式（两段扫）
   · 大赛会场很大 → interior 蛇形扫

用法：python scripts/add_all_city_scenes.py --emit
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "scripts" / "gen_scenes.py"

# 新增场景：名字 -> (mapId, x, y, 中文说明, 模式)
NEW = {
    # Oldale
    "dex_area_oldale":      None,   # 占位，不用
    # Dewford
    "center_dewford":       ("3:1",  7, 8,  "Dewford 宝可梦中心 1F", "counter"),
    # Lavaridge
    "herbshop_lavaridge":   ("4:0",  6, 8,  "Lavaridge 药草店", "counter_left"),
    "mart_lavaridge":       ("4:4",  7, 8,  "Lavaridge 商店", "counter"),
    "center_lavaridge":     ("4:5",  7, 8,  "Lavaridge 宝可梦中心 1F", "counter"),
    # Fallarbor
    "mart_fallarbor":       ("5:0",  7, 8,  "Fallarbor 商店", "counter"),
    "contest_fallarbor":    ("5:2", 10, 12, "Fallarbor 华丽大赛会场", "interior"),
    "center_fallarbor":     ("5:3",  7, 8,  "Fallarbor 宝可梦中心 1F", "counter"),
    # Verdanturf
    "contest_verdanturf_l": ("6:0",  8, 8,  "Verdanturf 大赛大厅", "interior"),
    "contest_verdanturf":   ("6:1", 10, 12, "Verdanturf 华丽大赛会场", "interior"),
    "mart_verdanturf":      ("6:2",  7, 8,  "Verdanturf 商店", "counter"),
    "center_verdanturf":    ("6:3",  7, 8,  "Verdanturf 宝可梦中心 1F", "counter"),
    # Pacifidlog
    "center_pacifidlog":    ("7:0",  7, 8,  "Pacifidlog 宝可梦中心 1F", "counter"),
    # Petalburg
    "gym_petalburg":        ("8:1",  8, 12, "Petalburg 道馆（普通）", "gym"),
    "center_petalburg":     ("8:4",  7, 8,  "Petalburg 宝可梦中心 1F", "counter"),
    "mart_petalburg":       ("8:6",  7, 8,  "Petalburg 商店", "counter"),
    # Slateport
    "contest_slateport_l":  ("9:2",  8, 8,  "Slateport 大赛大厅", "interior"),
    "fanclub_slateport":    ("9:5",  8, 10, "Slateport 宝可梦发烧友俱乐部", "interior"),
    "museum_slateport":     ("9:6",  8, 10, "Slateport 海洋博物馆 1F", "interior"),
    # Rustboro
    "center_rustboro":      ("11:5", 7, 8,  "Rustboro 宝可梦中心 1F", "counter"),
    "mart_rustboro":        ("11:7", 7, 8,  "Rustboro 商店", "counter"),
    # Fortree
    "gym_fortree":          ("12:1", 8, 12, "Fortree 道馆（飞行）", "gym"),
    "center_fortree":       ("12:2", 7, 8,  "Fortree 宝可梦中心 1F", "counter"),
    "mart_fortree":         ("12:4", 7, 8,  "Fortree 商店", "counter"),
    # Lilycove
    "contest_lilycove_l":   ("13:4", 8, 8,  "Lilycove 大赛大厅", "interior"),
    "center_lilycove":      ("13:6", 7, 8,  "Lilycove 宝可梦中心 1F", "counter"),
    # Mossdeep
    "gym_mossdeep":         ("14:0", 8, 12, "Mossdeep 道馆（超能）", "gym"),
    "center_mossdeep":      ("14:3", 7, 8,  "Mossdeep 宝可梦中心 1F", "counter"),
    "mart_mossdeep":        ("14:5", 7, 8,  "Mossdeep 商店", "counter"),
    # Sootopolis
    "gym_sootopolis":       ("15:0", 8, 12, "Sootopolis 道馆（水）1F", "gym"),
    "center_sootopolis":    ("15:2", 7, 8,  "Sootopolis 宝可梦中心 1F", "counter"),
    "mart_sootopolis":      ("15:4", 7, 8,  "Sootopolis 商店", "counter"),
}
NEW = {k: v for k, v in NEW.items() if v is not None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true")
    a = ap.parse_args()

    s = GEN.read_text(encoding="utf-8")
    # 找 SCENE_DEFS 的结束大括号
    m = re.search(r"SCENE_DEFS = \{\n(.*?)\n\}", s, re.S)
    if not m:
        print("[ERR] 找不到 SCENE_DEFS")
        return 1
    body = m.group(1)

    added = 0
    lines = []
    for name, (mp, x, y, desc, mode) in NEW.items():
        if f'"{name}"' in body:
            continue
        lines.append(f'    "{name}": ({mp!r}, {x}, {y}, {desc!r}, {mode!r}),')
        added += 1

    if not lines:
        print("[skip] 没有新场景要加")
    else:
        new_body = body + "\n" + "\n".join(lines)
        s = s[:m.start(1)] + new_body + s[m.end(1):]
        GEN.write_text(s, encoding="utf-8")
        print(f"[OK] 加入 {added} 个场景定义")

    if a.emit:
        import importlib.util
        spec = importlib.util.spec_from_file_location("g", GEN)
        g = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(g)
        n = 0
        for name in NEW:
            if name not in g.SCENE_DEFS:
                continue
            p = g.SCENES / f"{name}.lua"
            p.write_text(g.gen(name), encoding="utf-8")
            n += 1
        print(f"[OK] 生成 {n} 个场景文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
