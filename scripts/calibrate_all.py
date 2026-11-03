#!/usr/bin/env python3
"""批量校准所有「窗口数 ≤ 1」的场景，自动写回 gen_scenes.py 并重生成。

这是 calibrate_scenes.py 的批量版：自动从已采集的 run 里找出需要校准的场景，
不再需要手工列名单。

用法：
  python scripts/calibrate_all.py            # 只报告
  python scripts/calibrate_all.py --write    # 写回 + 重生成
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot" / "tools"))
GEN = ROOT / "scripts" / "gen_scenes.py"
BOTRUNS = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot"

EWRAM_BASE, EWRAM_LEN = 0x02000000, 0x40000
IWRAM_BASE = 0x03000000
TPL_BASE, TPL_STEP = 0x0C0C, 0x18
F_X, F_Y, F_SCRIPT = 0x00, 0x02, 0x0C

# 手工维护、不要自动改的场景
MANUAL = {"gym_dewford", "contest_lilycove"}


def s16(b, o): return int.from_bytes(b[o:o + 2], "little", signed=True)
def u32(b, o): return int.from_bytes(b[o:o + 4], "little")


def off_of(addr: int) -> int:
    return (EWRAM_LEN + (addr - IWRAM_BASE)) if addr >= IWRAM_BASE else (addr - EWRAM_BASE)


def win_count(run: Path) -> int:
    log = run / "origin" / "scene.log"
    if not log.is_file():
        return -1
    return len(re.findall(r"^\[win\]", log.read_text(encoding="utf-8",
                                                    errors="replace"), re.M))


def analyze(run: Path):
    side = run / "origin"
    if not side.is_dir():
        side = run / "translated"
    log = side / "scene.log"
    if not log.is_file():
        return None
    m = re.search(r"sb1=0x([0-9A-Fa-f]{8})",
                  log.read_text(encoding="utf-8", errors="replace"))
    if not m:
        return None
    sb1addr = int(m.group(1), 16)
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
    if not objs:
        return None
    # 选最近的对象，落点=其下方一格（朝 UP 对话）
    x, y, sp = min(objs, key=lambda t: abs(t[0] - px) + abs(t[1] - py))
    return mg, mn, x, y + 1, x, y, len(objs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    spec = importlib.util.spec_from_file_location("gen", GEN)
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)

    need = []
    for name in sorted(g.SCENE_DEFS):
        if name in MANUAL:
            continue
        d = BOTRUNS / name
        if not d.is_dir():
            continue
        runs = sorted([x for x in d.iterdir() if x.is_dir()], key=lambda x: x.name)
        if not runs:
            continue
        w = win_count(runs[-1])
        if 0 <= w <= 1:
            need.append(name)

    print(f"需要校准的场景：{len(need)} 个\n")
    results = {}
    for name in need:
        d = BOTRUNS / name
        runs = sorted([x for x in d.iterdir() if x.is_dir()], key=lambda x: x.name)
        info = analyze(runs[-1])
        if not info:
            print(f"  {name:<26} 解析失败")
            continue
        mg, mn, lx, ly, tx, ty, n = info
        print(f"  {name:<26} {mg}:{mn:<4} NPC({tx},{ty}) → 落({lx},{ly})  对象{n}个")
        results[name] = (f"{mg}:{mn}", lx, ly)

    if not results:
        print("\n没有可校准的")
        return 0
    if not a.write:
        print("\n（加 --write 写回并重生成）")
        return 0

    # 写回 gen_scenes.py（逐行，兼容单双引号）
    lines = GEN.read_text(encoding="utf-8").splitlines(keepends=True)
    n_ok = 0
    out = []
    for line in lines:
        m = re.match(r'^(\s*)"([^"]+)":(\s*\(\s*[\'"])([^\'"]+)([\'"],\s*)(\d+)(\s*,\s*)(\d+)(.*)$',
                     line.rstrip("\n"))
        if m and m.group(2) in results:
            nm = m.group(2)
            mp, lx, ly = results[nm]
            out.append(f'{m.group(1)}"{nm}":{m.group(3)}{mp}{m.group(5)}'
                       f'{lx}{m.group(7)}{ly}{m.group(9)}\n')
            n_ok += 1
        else:
            out.append(line)
    GEN.write_text("".join(out), encoding="utf-8")
    print(f"\n[OK] 写回 {n_ok} 处落点")

    # 重生成
    spec = importlib.util.spec_from_file_location("gen2", GEN)
    g2 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g2)
    n = 0
    for name in results:
        if name in g2.SCENE_DEFS:
            (g2.SCENES / f"{name}.lua").write_text(g2.gen(name), encoding="utf-8")
            n += 1
    print(f"[OK] 重生成 {n} 个场景文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
