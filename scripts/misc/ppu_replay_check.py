#!/usr/bin/env python3
"""scripts/misc/ppu_replay_check.py — 验证「离线重放 == bot 实际渲染」

## 这个脚本是干什么的

`src/util/gba_ppu.py` 声称「用 bot 的运行时快照能重放出屏幕上那一帧」。
本脚本把这句话变成**可证伪的实测**：拿 bot 已采集的
`NNN.{vram,pal,oam,io}.bin` 重放，与 bot 同一帧存的 `NNN.png` 逐像素比对。

一致率 100% ⇒ 重放器可信，可以拿它批量导出「和屏幕一样」的图。
一致率低 ⇒ 打印 trace（用了哪些假设）+ 差异分布，定位是哪个假设错了。

## 用法

    C:/Python314/python.exe scripts/misc/ppu_replay_check.py
    C:/Python314/python.exe scripts/misc/ppu_replay_check.py --scene bag --limit 8
    C:/Python314/python.exe scripts/misc/ppu_replay_check.py --all --limit 200
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

from util.gba_ppu import RenderTrace, Snapshot, compare, render   # noqa: E402


def find_runs(scene: str | None, side: str) -> list[Path]:
    base = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot"
    if scene:
        return sorted(base.glob(f"{scene}/*/{side}"))
    return sorted(base.glob(f"*/**/{side}"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default=None, help="只测某个场景目录名")
    ap.add_argument("--side", default="origin", choices=["origin", "translated"])
    ap.add_argument("--limit", type=int, default=6, help="每个 run 最多测几帧")
    ap.add_argument("--all", action="store_true", help="跑所有场景（默认只跑前 3 个 run）")
    ap.add_argument("--min-ratio", type=float, default=0.999,
                    help="判为一致的一致率下限")
    args = ap.parse_args()

    runs = find_runs(args.scene, args.side)
    if not args.all:
        runs = runs[:3]
    if not runs:
        print("[ERR] 没找到 bot 采集目录")
        return 1

    print(f"测试 {len(runs)} 个 run，每 run 最多 {args.limit} 帧，"
          f"一致率门槛 {args.min_ratio:.4%}\n")

    tot = 0
    ok = 0
    ratios: list[float] = []
    fails: list[tuple[str, float, str]] = []

    for d in runs:
        frames = sorted(p.stem for p in d.glob("*.png"))
        frames = [f for f in frames if f.isdigit()][:args.limit]
        for f in frames:
            try:
                snap = Snapshot.load(d, f)
            except FileNotFoundError:
                continue
            tr = RenderTrace()
            img = render(snap, trace=tr)
            r = compare(img, d / f"{f}.png")
            tot += 1
            ratio = r["ratio"]
            ratios.append(ratio)
            tag = "OK " if ratio >= args.min_ratio else "DIFF"
            if ratio >= args.min_ratio:
                ok += 1
            else:
                fails.append((f"{d.parent.parent.name}/{d.parent.name}/{f}",
                              ratio, str(tr)))
            print(f"  [{tag}] {d.parent.parent.name}/{d.parent.name}/{f} "
                  f"{ratio:7.2%}  {tr}")

    print(f"\n{'='*60}")
    print(f"总计 {tot} 帧，一致 {ok} 帧（{ok/tot:.1%}），"
          f"平均一致率 {np.mean(ratios):.2%}")
    if fails:
        print(f"\n不一致 {len(fails)} 帧（前 10）:")
        for name, ratio, tr in fails[:10]:
            print(f"  {name}: {ratio:.2%}\n     {tr}")
    return 0 if ok == tot else 2


if __name__ == "__main__":
    raise SystemExit(main())
