#!/usr/bin/env python3
"""scripts/misc/sprite_extract_probe.py — 量化「运行时精灵提取」的精确率

## 回答的问题

从 bot 采集的运行时快照（OAM + VRAM + CGRAM）提取出的 sprite，
有多少在屏幕截图上能**逐像素 100% 命中**？

这是「导出图和 bot 实际渲染一致」的硬指标：只要 sprite 在截图里
同位置同像素，它就是屏幕上那张图，与「人猜调色板/拼合」的静态导出
有本质区别。

## 为什么这条路能成

OBJ 精灵的**全部参数都在 OAM 里**（tile 号、调色板 bank、翻转、尺寸、
位置），不受 GBA 只写寄存器的限制。实测 bag/title 场景里 4/5、6/7 个
OBJ 精确 100%。

## 为什么 BG 层不行

BG 文本层需要 BGxHOFS/VOFS（卷动），仿射层需要 PA/PB/PC/PD —— 全是
**只写寄存器**，读回来是 open bus（实测 0x1C10 垃圾）。所以 BG 层
离线重放只在「卷动=0 的纯 UI 界面」才准。

## 用法

    C:/Python314/python.exe scripts/misc/sprite_extract_probe.py --scene bag
    C:/Python314/python.exe scripts/misc/sprite_extract_probe.py --all --limit-runs 30
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np                                    # noqa: E402
from PIL import Image                                 # noqa: E402

from util.gba_ppu import SCREEN_H, SCREEN_W, Snapshot, parse_oam   # noqa: E402


def check_frame(d: Path, frame: str, tol: int = 0) -> tuple[int, int, int]:
    """返回 (可见 OBJ 数, 精确命中数, 总不透明像素)。"""
    snap = Snapshot.load(d, frame)
    if not snap.obj_on:
        return 0, 0, 0
    png = d / f"{frame}.png"
    if not png.is_file():
        return 0, 0, 0
    ref = np.asarray(Image.open(png).convert("RGB")).astype(np.int16)
    objs = parse_oam(snap)
    n_ok = 0
    n_px = 0
    for o in objs:
        # 正确处理出屏：左上角裁掉的部分要从 sprite 内部对应偏移取
        x0, y0 = max(0, o.x), max(0, o.y)
        sx, sy = x0 - o.x, y0 - o.y
        w = min(o.w - sx, SCREEN_W - x0)
        h = min(o.h - sy, SCREEN_H - y0)
        if w <= 0 or h <= 0:
            continue
        sub = o.rgb[sy:sy + h, sx:sx + w].astype(np.int16)
        m = o.mask[sy:sy + h, sx:sx + w]
        op = ~m
        n = int(op.sum())
        if n == 0:
            continue
        n_px += n
        eq = (np.abs(sub - ref[y0:y0 + h, x0:x0 + w]).max(axis=2) <= tol)
        if (eq & op).sum() == n:
            n_ok += 1
    return len(objs), n_ok, n_px


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default=None)
    ap.add_argument("--side", default="origin", choices=["origin", "translated"])
    ap.add_argument("--limit-runs", type=int, default=3)
    ap.add_argument("--limit-frames", type=int, default=4)
    ap.add_argument("--tol", type=int, default=0,
                    help="允许的通道误差（0 = 严格逐像素）")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    base = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot"
    if args.scene:
        runs = sorted(base.glob(f"{args.scene}/*/{args.side}"))
    else:
        runs = sorted(base.glob(f"*/**/{args.side}"))
        runs = [r for r in runs if not r.parent.parent.name.startswith("_")]
    if not args.all:
        runs = runs[:args.limit_runs]
    if not runs:
        print("[ERR] 无采集目录")
        return 1

    tot_obj = tot_ok = 0
    frames = 0
    per_scene: dict[str, list[int]] = {}

    for d in runs:
        pngs = sorted(p for p in d.glob("*.png") if p.stem.isdigit())
        pngs = pngs[:args.limit_frames]
        for p in pngs:
            try:
                n_obj, n_ok, n_px = check_frame(d, p.stem, args.tol)
            except (FileNotFoundError, ValueError):
                continue
            if n_obj == 0:
                continue
            frames += 1
            tot_obj += n_obj
            tot_ok += n_ok
            sc = d.parent.parent.name
            s = per_scene.setdefault(sc, [0, 0])
            s[0] += n_obj
            s[1] += n_ok

    print(f"扫描 {frames} 帧（{len(runs)} 个 run，容差 ±{args.tol}）")
    print(f"可见 OBJ {tot_obj} 个，逐像素精确命中 {tot_ok} 个 "
          f"({tot_ok/tot_obj:.1%})\n")

    print("按场景（只列有 OBJ 的）:")
    for sc, (n, k) in sorted(per_scene.items(), key=lambda kv: -kv[1][0])[:25]:
        print(f"  {sc:24s} {k:4d}/{n:4d}  {k/n:5.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
