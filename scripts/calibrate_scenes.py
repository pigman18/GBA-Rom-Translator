#!/usr/bin/env python3
"""批量校准落点：读每个场景的 ram 帧，解出可交互对象，给出最佳落点。

── 为什么需要这一步 ────────────────────────────────────────────────────
31 个新城市场景里有 6 个只有 1 帧窗口（其余都 164~315 帧）。
原因都是「落点离 NPC 太远/方向不对」。用 list_interactables 的同一套逻辑
（ObjectEventTemplate，日版布局 SaveBlock1+0x0C0C / step 0x18）
逐个解出最近的带 script 对象，直接把落点定到它旁边。

输出一份可直接粘进 gen_scenes.py 的 SCENE_DEFS 片段。

用法：python scripts/calibrate_scenes.py [--write]
  --write  直接把校准后的落点写回 gen_scenes.py
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot" / "tools"))

EWRAM_BASE, EWRAM_LEN = 0x02000000, 0x40000
IWRAM_BASE = 0x03000000
TPL_BASE, TPL_STEP = 0x0C0C, 0x18
F_X, F_Y, F_SCRIPT = 0x00, 0x02, 0x0C

# 需要校准的场景（实测只有 1 帧窗口的）
TARGETS = [
    "herbshop_lavaridge", "contest_fallarbor", "contest_verdanturf_l",
    "gym_petalburg", "contest_slateport_l", "museum_slateport",
]


def s16(b, o): return int.from_bytes(b[o:o + 2], "little", signed=True)
def u32(b, o): return int.from_bytes(b[o:o + 4], "little")


def off_of(addr: int) -> int:
    return (EWRAM_LEN + (addr - IWRAM_BASE)) if addr >= IWRAM_BASE else (addr - EWRAM_BASE)


def analyze(run: Path):
    """返回 (map_g, map_n, px, py, [(x,y,script)...])。"""
    side = run / "translated"
    if not side.is_dir():
        side = run / "origin"
    sb1addr = None
    log = side / "scene.log"
    if log.is_file():
        m = re.search(r"sb1=0x([0-9A-Fa-f]{8})",
                      log.read_text(encoding="utf-8", errors="replace"))
        if m:
            sb1addr = int(m.group(1), 16)
    if sb1addr is None:
        return None
    # 取最后一帧（那时已经到位）
    frames = sorted(side.glob("*.ram.bin"))
    if not frames:
        return None
    data = frames[-1].read_bytes()
    o = off_of(sb1addr)
    sb1 = data[o:o + 0x3AC0]
    if len(sb1) < 0x3AC0:
        return None
    mg, mn = sb1[4], sb1[5]
    px, py = s16(sb1, 0), s16(sb1, 2)
    objs = []
    for i in range(64):
        p = TPL_BASE + i * TPL_STEP
        if p + TPL_STEP > len(sb1):
            break
        x, y = s16(sb1, p + F_X), s16(sb1, p + F_Y)
        sp = u32(sb1, p + F_SCRIPT)
        if 0x08000000 <= sp < 0x0A000000 and 0 <= x <= 120 and 0 <= y <= 120:
            objs.append((x, y, sp))
    return mg, mn, px, py, objs


def best_spot(objs, px, py):
    """选最近的对象，落点取它的下方一格（朝 UP 对话）。"""
    if not objs:
        return None
    x, y, sp = min(objs, key=lambda t: abs(t[0] - px) + abs(t[1] - py))
    return x, y + 1, x, y, sp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    results = {}
    print(f"{'场景':<24} {'地图':<8} {'NPC':<12} {'建议落点':<12}")
    print("-" * 62)
    for name in TARGETS:
        run_dir = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot" / name
        if not run_dir.is_dir():
            print(f"{name:<24} 无采集记录")
            continue
        runs = sorted([d for d in run_dir.iterdir() if d.is_dir()],
                      key=lambda d: d.name)
        if not runs:
            print(f"{name:<24} 空目录")
            continue
        info = analyze(runs[-1])
        if not info:
            print(f"{name:<24} 解析失败")
            continue
        mg, mn, px, py, objs = info
        spot = best_spot(objs, px, py)
        if not spot:
            print(f"{name:<24} {mg}:{mn:<6} 无可交互对象")
            continue
        lx, ly, tx, ty, sp = spot
        print(f"{name:<24} {mg}:{mn:<6} ({tx},{ty})    ({lx},{ly})")
        results[name] = (f"{mg}:{mn}", lx, ly)

    print(f"\n共校准 {len(results)} 个场景")
    if a.write and results:
        gen = ROOT / "scripts" / "gen_scenes.py"
        s = gen.read_text(encoding="utf-8")
        n = 0
        # 逐行处理：每行形如 `    "name": ("g:n", X, Y, "说明", "模式"),`
        # 用「行首 name 定位 + 该行内的两个数字」替换，避免跨行匹配。
        out_lines = []
        for line in s.splitlines(keepends=True):
            # 注意：add_all_city_scenes.py 写入时用的是**单引号**（repr 产物），
            # 而原有条目用双引号 —— 正则必须同时接受两种。
            mline = re.match(
                r'^(\s*)"([^"]+)":(\s*\(\s*[\'"])([^\'"]+)([\'"],\s*)(\d+)(\s*,\s*)(\d+)(.*)$',
                line.rstrip("\n"))
            if mline and mline.group(2) in results:
                nm = mline.group(2)
                mp, lx, ly = results[nm]
                newline = (f'{mline.group(1)}"{nm}":{mline.group(3)}{mp}'
                           f'{mline.group(5)}{lx}{mline.group(7)}{ly}{mline.group(9)}')
                out_lines.append(newline + "\n")
                n += 1
            else:
                out_lines.append(line)
        s = "".join(out_lines)
        gen.write_text(s, encoding="utf-8")
        print(f"[OK] 写回 {n} 处落点")
        print("     记得再跑 gen_scenes.py --emit 重新生成场景文件")
    else:
        print("（加 --write 写回 gen_scenes.py）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
