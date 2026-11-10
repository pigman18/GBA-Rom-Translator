#!/usr/bin/env python3
"""验证 ObjectEventTemplate 是否真的随地图刷新。

── 疑点 ────────────────────────────────────────────────────────────────
house_mauville2 (10:4) 和 motel_lilycove_2f (13:1) 是两张完全不同的地图，
但用 SaveBlock1+0x0C0C 解出的可交互对象坐标**一模一样**：
    (1,3) (5,4) (5,5)
而那三个坐标正是**商店 (10:7)** 的对象 —— 我在最早验证时见过。

⇒ 说明 template 区**没有随地图刷新**，或者刷新时机晚于我采帧的时刻。

── 本脚本验证 ──────────────────────────────────────────────────────────
对同一场景的**多个帧**分别解对象，看它们是否变化：
  · 若从一开始就固定 → template 确实没刷新（结论：这个方法不可用于定位）
  · 若后期才变 → 说明需要等地图完全加载后再读

用法：python scripts/verify_template_refresh.py <scene名>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOTRUNS = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot"

EWRAM_BASE, EWRAM_LEN = 0x02000000, 0x40000
IWRAM_BASE = 0x03000000
TPL_BASE, TPL_STEP = 0x0C0C, 0x18
F_X, F_Y, F_SCRIPT = 0x00, 0x02, 0x0C


def s16(b, o): return int.from_bytes(b[o:o + 2], "little", signed=True)
def u32(b, o): return int.from_bytes(b[o:o + 4], "little")


def off_of(a: int) -> int:
    return (EWRAM_LEN + (a - IWRAM_BASE)) if a >= IWRAM_BASE else (a - EWRAM_BASE)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    name = sys.argv[1]
    d = BOTRUNS / name
    runs = sorted([x for x in d.iterdir() if x.is_dir()], key=lambda x: x.name)
    if not runs:
        print("[ERR] 没有 run")
        return 1
    run = runs[-1]
    side = run / "origin"
    log = side / "scene.log"
    txt = log.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"sb1=0x([0-9A-Fa-f]{8})", txt)
    if not m:
        print("[ERR] 没有 sb1")
        return 1
    sb1 = int(m.group(1), 16)
    frames = sorted(side.glob("*.ram.bin"))
    print(f"{name}  run={run.name}  共 {len(frames)} 帧")
    print(f"{'帧':<6} {'map':<8} {'pos':<10} 可交互对象坐标")
    print("-" * 76)
    prev = None
    for f in frames[::max(1, len(frames) // 10)][:12]:
        data = f.read_bytes()
        o = off_of(sb1)
        seg = data[o:o + 0x3AC0]
        mg, mn = seg[4], seg[5]
        px, py = s16(seg, 0), s16(seg, 2)
        coords = []
        for i in range(64):
            p = TPL_BASE + i * TPL_STEP
            if p + TPL_STEP > len(seg):
                break
            x, y = s16(seg, p + F_X), s16(seg, p + F_Y)
            sp = u32(seg, p + F_SCRIPT)
            if 0x08000000 <= sp < 0x0A000000 and 0 <= x <= 120 and 0 <= y <= 120:
                coords.append((x, y))
        sig = tuple(coords)
        same = "  (同上一帧)" if sig == prev else ""
        print(f"{f.stem:<6} {mg}:{mn:<6} ({px},{py})    "
              f"{coords[:6]}{same}")
        prev = sig
    print("\n判读：若坐标从头到尾不变且与商店一致 ⇒ template 没随地图刷新，")
    print("      这个方法不能用来定位 NPC（我之前用它校准过的场景要复核）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
