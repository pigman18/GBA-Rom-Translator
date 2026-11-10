#!/usr/bin/env python3
"""把剩余 60 个零散建筑加进 gen_scenes.py 并生成场景。

── 分三类 ────────────────────────────────────────────────────────────
1. **Houses（民家）**：小房间，通常 1-2 个 NPC。用 `interior` 模式
   （蛇形走位 + 每格四方向试 A）。
2. **PokemonCenter_2F（PC 二楼）**：无线俱乐部 / 交换中心 / 战斗塔入口等，
   文本较多。用 `interior`。
3. **专营店/机构**：Devon 公司 3 层、船厂 2 层、博物馆 2F、港口、
   百货商场、华丽大赛大厅、装饰店等。用 `interior` 或 `counter`。

── 落点策略 ──────────────────────────────────────────────────────────
先全部用「中心落点 + 通用模板」批量生成，跑完后用
`scripts/calibrate_scenes.py` 统一校准（它读 ram 帧自动算 NPC 位置）。

用法：python scripts/add_remaining_buildings.py --emit
"""
from __future__ import annotations

import argparse
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "scripts" / "gen_scenes.py"
sys_path = ROOT / "scripts"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# 名字 -> (mapId, x, y, 中文说明, 模式)
# 落点先统一取 (8,8)（室内中心偏下），跑完再 calibrate。
NEW: dict[str, tuple] = {}


def add(name: str, mid: str, desc: str, mode: str, x: int = 8, y: int = 8):
    NEW[name] = (mid, x, y, desc, mode)


def build() -> None:
    # ── Oldale ──
    add("house_oldale1", "2:0", "Oldale 民家 1", "interior")
    add("house_oldale2", "2:1", "Oldale 民家 2", "interior")
    add("center_oldale_2f", "2:3", "Oldale 宝可梦中心 2F", "interior")

    # ── Dewford ──
    add("house_dewford1", "3:0", "Dewford 民家 1", "interior")
    add("center_dewford_2f", "3:2", "Dewford 宝可梦中心 2F", "interior")
    add("hall_dewford", "3:4", "Dewford 会馆", "interior")
    add("house_dewford2", "3:5", "Dewford 民家 2", "interior")

    # ── Lavaridge ──
    add("gym_lavaridge_b1f", "4:2", "Lavaridge 道馆 B1F", "gym")
    add("house_lavaridge", "4:3", "Lavaridge 民家", "interior")
    add("center_lavaridge_2f", "4:6", "Lavaridge 宝可梦中心 2F", "interior")

    # ── Fallarbor ──
    add("center_fallarbor_2f", "5:4", "Fallarbor 宝可梦中心 2F", "interior")
    add("house_fallarbor1", "5:5", "Fallarbor 民家 1", "interior")
    add("house_fallarbor2", "5:6", "Fallarbor 民家 2", "interior")

    # ── Verdanturf ──
    add("center_verdanturf_2f", "6:4", "Verdanturf 宝可梦中心 2F", "interior")
    add("house_wanda", "6:5", "Verdanturf 瓦妮达家", "interior")
    add("house_friendship", "6:6", "Verdanturf 鉴定之家", "interior")
    add("house_verdanturf", "6:7", "Verdanturf 民家", "interior")

    # ── Pacifidlog ──
    add("center_pacifidlog_2f", "7:1", "Pacifidlog 宝可梦中心 2F", "interior")
    for i in range(5):
        add(f"house_pacifidlog{i+1}", f"7:{2+i}", f"Pacifidlog 民家 {i+1}", "interior")

    # ── Petalburg ──
    add("house_wally", "8:0", "Petalburg 小胜家", "interior")
    add("house_petalburg1", "8:2", "Petalburg 民家 1", "interior")
    add("house_petalburg2", "8:3", "Petalburg 民家 2", "interior")
    add("center_petalburg_2f", "8:5", "Petalburg 宝可梦中心 2F", "interior")

    # ── Slateport ──
    add("shipyard_slateport_1f", "9:0", "Slateport 船厂 1F", "interior")
    add("shipyard_slateport_2f", "9:1", "Slateport 船厂 2F", "interior")
    add("house_slateport1", "9:4", "Slateport 民家 1", "interior")
    add("museum_slateport_2f", "9:7", "Slateport 海洋博物馆 2F", "interior")
    add("harbor_slateport", "9:8", "Slateport 港口", "interior")
    add("house_slateport2", "9:9", "Slateport 民家 2", "interior")
    add("center_slateport_2f", "9:11", "Slateport 宝可梦中心 2F", "interior")

    # ── Mauville ──
    add("house_mauville1", "10:2", "Mauville 民家 1", "interior")
    add("house_mauville2", "10:4", "Mauville 民家 2", "interior")
    add("center_mauville_2f", "10:6", "Mauville 宝可梦中心 2F", "interior")

    # ── Rustboro ──
    add("devon_1f", "11:0", "Rustboro Devon 公司 1F", "interior")
    add("devon_2f", "11:1", "Rustboro Devon 公司 2F", "interior")
    add("devon_3f", "11:2", "Rustboro Devon 公司 3F", "interior")
    add("school_rustboro", "11:4", "Rustboro 宝可梦学校", "interior")
    add("center_rustboro_2f", "11:6", "Rustboro 宝可梦中心 2F", "interior")

    # ── Fortree ──
    add("house_fortree1", "12:0", "Fortree 民家 1", "interior")
    add("center_fortree_2f", "12:3", "Fortree 宝可梦中心 2F", "interior")
    for i in range(4):
        add(f"house_fortree{i+2}", f"12:{5+i}", f"Fortree 民家 {i+2}", "interior")
    add("decor_fortree", "12:9", "Fortree 装饰店", "counter")

    # ── Lilycove ──
    add("motel_lilycove_1f", "13:0", "Lilycove 旅馆 1F", "interior")
    add("motel_lilycove_2f", "13:1", "Lilycove 旅馆 2F", "interior")
    add("museum_lilycove_1f", "13:2", "Lilycove 美术馆 1F", "interior")
    add("museum_lilycove_2f", "13:3", "Lilycove 美术馆 2F", "interior")
    add("center_lilycove_2f", "13:7", "Lilycove 宝可梦中心 2F", "interior")

    # ── Mossdeep ──
    add("house_mossdeep1", "14:1", "Mossdeep 民家 1", "interior")
    add("house_mossdeep2", "14:2", "Mossdeep 民家 2", "interior")
    add("center_mossdeep_2f", "14:4", "Mossdeep 宝可梦中心 2F", "interior")

    # ── Sootopolis ──
    add("gym_sootopolis_b1f", "15:1", "Sootopolis 道馆 B1F", "gym")
    add("center_sootopolis_2f", "15:3", "Sootopolis 宝可梦中心 2F", "interior")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true")
    a = ap.parse_args()

    build()
    s = GEN.read_text(encoding="utf-8")
    m = re.search(r"SCENE_DEFS = \{\n(.*?)\n\}", s, re.S)
    if not m:
        print("[ERR] 找不到 SCENE_DEFS")
        return 1
    body = m.group(1)

    lines = []
    for name, (mp, x, y, desc, mode) in NEW.items():
        if f'"{name}"' in body:
            continue
        lines.append(f'    "{name}": ("{mp}", {x}, {y}, "{desc}", "{mode}"),')
    if lines:
        s = s[:m.start(1)] + body + "\n" + "\n".join(lines) + s[m.end(1):]
        GEN.write_text(s, encoding="utf-8")
        print(f"[OK] 加入 {len(lines)} 个场景定义")
    else:
        print("[skip] 无新增")

    if a.emit:
        g = load("gen_scenes", GEN)
        n = 0
        for name in NEW:
            if name not in g.SCENE_DEFS:
                continue
            (g.SCENES / f"{name}.lua").write_text(g.gen(name), encoding="utf-8")
            n += 1
        print(f"[OK] 生成 {n} 个场景文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
