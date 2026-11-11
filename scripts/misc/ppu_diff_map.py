#!/usr/bin/env python3
"""scripts/misc/ppu_diff_map.py — 重放 vs 截图差异定位图

把 diff 画成三格：参考 / 重放 / 差异热区（红=不同）。
用于一眼看出差异是「整层错位」还是「局部几块」。

    C:/Python314/python.exe scripts/misc/ppu_diff_map.py --scene bag --frame 003
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np                                  # noqa: E402
from PIL import Image                               # noqa: E402

from util.gba_ppu import Snapshot, render           # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bag")
    ap.add_argument("--frame", default="003")
    ap.add_argument("--side", default="origin")
    ap.add_argument("--run", default=None)
    ap.add_argument("--out", default="work/_ppu_diag")
    args = ap.parse_args()

    base = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot" / args.scene
    runs = sorted(base.glob(f"*/{args.side}"))
    d = Path(args.run) / args.side if args.run else runs[-1]
    snap = Snapshot.load(d, args.frame)
    ref = np.asarray(Image.open(d / f"{args.frame}.png").convert("RGB"))
    got = render(snap)

    diff = np.abs(ref.astype(np.int16) - got.astype(np.int16)).max(axis=2)
    bad = diff > 0

    print(f"帧 {args.frame}  不同像素 {bad.sum()} / {bad.size} "
          f"({bad.sum()/bad.size:.2%})")

    # 差异按 8x8 tile 聚合成网格，打印哪几个 tile 块错
    th, tw = ref.shape[0] // 8, ref.shape[1] // 8
    grid = bad.reshape(th, 8, tw, 8).sum(axis=(1, 3))
    rows = []
    for y in range(th):
        for x in range(tw):
            if grid[y, x] > 0:
                rows.append((int(grid[y, x]), x, y))
    rows.sort(reverse=True)
    print(f"涉及 {len(rows)} 个 8x8 块，最差的 15 个 (tile_x, tile_y, 错像素数):")
    for n, x, y in rows[:15]:
        print(f"  ({x:2d},{y:2d}) {n:3d}px")

    # 输出对比图
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    heat = ref.copy()
    heat[bad] = (255, 0, 0)
    combo = Image.new("RGB", (ref.shape[1] * 3 + 8, ref.shape[0]), (30, 30, 30))
    combo.paste(Image.fromarray(ref), (0, 0))
    combo.paste(Image.fromarray(got), (ref.shape[1] + 4, 0))
    combo.paste(Image.fromarray(heat), (ref.shape[1] * 2 + 8, 0))
    p = out / f"diff_{args.scene}_{args.frame}.png"
    combo.save(p)
    print(f"\n参考 | 重放 | 差异 -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
