#!/usr/bin/env python3
"""scripts/misc/ppu_layer_diag.py — 逐层诊断：重放的哪一层和截图不符

## 为什么需要它

`ppu_replay_check.py` 只给一个总一致率。总一致率低时看不出是 BG0 还是 OBJ
错了。本脚本把每个 BG 层单独渲染出来，与截图的对应像素比对，并打印每层
的实际颜色命中率 —— 直接告诉你「BG0 对了，BG2 完全错」这种结论。

判定方法：对每一层，统计「该层不透明像素」在截图里是否同色。
注意 BG 层会被上层覆盖，所以只看「该层不被更高优先级层遮挡」的像素。
简化：先算该层全部不透明像素，再看其中与截图同色的比例（被遮挡的会算成
不一致，但这能作为相对排序信号）。

## 用法

    C:/Python314/python.exe scripts/misc/ppu_layer_diag.py --scene bag --frame 001
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np                                  # noqa: E402
from PIL import Image                               # noqa: E402

from util.gba_ppu import (                          # noqa: E402
    SCREEN_H, SCREEN_W, Snapshot, bg_text_layer, cgram_to_rgb, parse_oam,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bag")
    ap.add_argument("--frame", default="001")
    ap.add_argument("--run", default=None, help="具体 run 目录名，缺省取最新")
    ap.add_argument("--out", default="work/_ppu_diag")
    args = ap.parse_args()

    base = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot" / args.scene
    runs = sorted(base.glob("*/origin"))
    if not runs:
        print("[ERR] 无采集目录")
        return 1
    d = Path(args.run) if args.run else runs[-1]
    if not d.name == "origin":
        d = d / "origin"
    print(f"run: {d}\n")

    snap = Snapshot.load(d, args.frame)
    ref = np.asarray(Image.open(d / f"{args.frame}.png").convert("RGB"))
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)

    print(f"DISPCNT={snap.dispcnt:04X} mode={snap.mode} "
          f"obj_1d={snap.obj_1d} force_blank={snap.force_blank}")
    print(f"BG on: {[snap.bg_on(b) for b in range(4)]}  OBJ on: {snap.obj_on}")
    for b in range(4):
        v = snap.bgcnt(b)
        print(f"  BG{b}CNT={v:04X} pri={v&3} cb={(v>>2)&3} "
              f"sb={(v>>8)&0x1F} 8bpp={bool(v&0x80)} size={(v>>14)&3}")
    print()

    # 背景色
    bd = cgram_to_rgb(snap.pal, 0, 1)[0]
    bg_only = np.zeros((SCREEN_H, SCREEN_W, 3), dtype=np.uint8)
    bg_only[:] = bd
    n_bd = int((ref == bd).all(axis=2).sum())
    print(f"背景色 {tuple(bd)} 在截图中占 {n_bd} px ({n_bd/(SCREEN_W*SCREEN_H):.1%})")
    print()

    # 逐层
    for b in range(4):
        if not snap.bg_on(b):
            continue
        img, mask = bg_text_layer(snap, b)
        opaque = ~mask
        if opaque.sum() == 0:
            print(f"BG{b}: 全透明")
            continue
        same = (img[opaque] == ref[opaque]).all(axis=1)
        print(f"BG{b}: 不透明 {opaque.sum():6d} px，与截图同色 {same.sum():6d} "
              f"({same.mean():6.1%})")
        Image.fromarray(img).save(out / f"layer_bg{b}.png")
        vis = img.copy()
        vis[mask] = (255, 0, 255)
        Image.fromarray(vis).save(out / f"layer_bg{b}_mask.png")

    # OBJ
    objs = parse_oam(snap) if snap.obj_on else []
    print(f"\nOBJ 可见 {len(objs)} 个:")
    for o in objs:
        print(f"  [{o.index}] pos=({o.x},{o.y}) {o.w}x{o.h} tile={o.tile_no} "
              f"pal={o.palbank} pri={o.priority} bpp8={o.bpp8} "
              f"flip={'H' if o.hflip else ''}{'V' if o.vflip else ''} "
              f"affine={o.affine}")
        Image.fromarray(o.rgb).save(out / f"obj_{o.index:03d}.png")

    # 参考图 + 拼接对比
    Image.fromarray(ref).save(out / f"ref_{args.frame}.png")
    print(f"\n产物 -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
