#!/usr/bin/env python3
"""scripts/misc/tiles_vs_screen.py — 导出资源 vs 屏幕实拍 的匹配验证

## 回答的问题

`tiles_patcher.py` 导出的 PNG，到底和游戏屏幕上显示的是不是同一张图？

做法：把导出图当作模板，在 bot 采集的截图里**全屏搜索最佳匹配位置**，
报告「最佳位置 + 该位置的一致率 + 第二名的差距」。这比人眼看可靠：

  · 一致率 100% 且位置唯一  ⇒ 导出的就是屏幕上那张，且颜色/像素完全对
  · 一致率高但位置有多个     ⇒ 图形重复（如通用图标），仍然对
  · 一致率低                 ⇒ 导出错了（调色板/拼合/bpp 猜错）

## 用法

    # 单个导出图，在指定截图里找
    C:/Python314/python.exe scripts/misc/tiles_vs_screen.py \
        --png work/POKEMON_RUBY_AXVJ00/tiles/0x0836D268_compose.png \
        --shot work/POKEMON_RUBY_AXVJ00/bot/title_menu/XXX/origin/001.png

    # 整套属性图标，在战斗/摘要截图里找
    C:/Python314/python.exe scripts/misc/tiles_vs_screen.py --prefix 0x087EE9C8 --scene battle
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np                                    # noqa: E402
from PIL import Image                                 # noqa: E402


def match_template(shot: np.ndarray, tpl: np.ndarray, tpl_alpha=None,
                   step: int = 1) -> list[tuple[float, int, int]]:
    """在 shot 里滑窗搜索 tpl，返回 [(一致率, x, y)] 降序。

    只统计 tpl 不透明的像素（alpha>0），透明区不参与比对 —— 否则导出图的
    透明背景会跟屏幕背景硬比，把正确匹配也拉低。
    """
    sh, sw = shot.shape[:2]
    th, tw = tpl.shape[:2]
    if th > sh or tw > sw:
        return []
    if tpl_alpha is None:
        tpl_alpha = np.ones((th, tw), dtype=bool)
    else:
        tpl_alpha = tpl_alpha > 0
    n = int(tpl_alpha.sum())
    if n == 0:
        return []

    results = []
    shot_i = shot.astype(np.int16)
    tpl_i = tpl.astype(np.int16)
    for y in range(0, sh - th + 1, step):
        for x in range(0, sw - tw + 1, step):
            win = shot_i[y:y + th, x:x + tw]
            eq = (win == tpl_i).all(axis=2)
            ratio = float((eq & tpl_alpha).sum()) / n
            if ratio > 0.5:
                results.append((ratio, x, y))
    results.sort(reverse=True)
    return results


def match_reverse(tpl: np.ndarray, shot: np.ndarray, tpl_alpha=None,
                  step: int = 1) -> list[tuple[float, int, int]]:
    """反方向：在**导出图**里搜索**屏幕截图**。

    为什么要反着搜：导出图常比屏幕大（标题 logo 是 256x256，屏幕 240x160），
    正向搜根本放不下。反着搜问的是另一个等价问题：
    「屏幕上看到的那一块，在导出图的哪个位置？像不像？」
    这对「导出图是不是屏幕那张图」同样是充分证据，且不受尺寸限制。

    注意掩码要换成**截图的**（截图没有 alpha，全部像素参与比对）；
    导出图的 alpha 在这一步没有意义 —— 导出图是「容器」，不是模板。
    """
    sh, sw = shot.shape[:2]
    return match_template(tpl, shot, np.ones((sh, sw), dtype=bool), step)


def load_png(p: Path):
    im = Image.open(p).convert("RGBA")
    arr = np.asarray(im)
    return arr[:, :, :3], arr[:, :, 3]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", help="单个导出图")
    ap.add_argument("--prefix", help="导出图前缀（批量，如 0x087EE9C8）")
    ap.add_argument("--tiles-dir", default="work/POKEMON_RUBY_AXVJ00/tiles")
    ap.add_argument("--shot", help="单张截图")
    ap.add_argument("--scene", help="场景名（自动取最新 origin 目录的全部截图）")
    ap.add_argument("--frame", default=None, help="场景模式下只看某一帧")
    ap.add_argument("--top", type=int, default=3)
    args = ap.parse_args()

    tiles_dir = ROOT / args.tiles_dir
    if args.png:
        pngs = [ROOT / args.png]
    elif args.prefix:
        pngs = sorted(tiles_dir.glob(f"{args.prefix}_*.png"))
        pngs = [p for p in pngs if p.stem.split("_")[-1].isdigit()]
    else:
        print("[ERR] 需要 --png 或 --prefix")
        return 1
    if not pngs:
        print("[ERR] 没找到导出图")
        return 1

    shots: list[Path] = []
    if args.shot:
        shots = [ROOT / args.shot]
    elif args.scene:
        base = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "bot" / args.scene
        runs = sorted(base.glob("*/origin"))
        if not runs:
            print(f"[ERR] 场景 {args.scene} 没有采集目录")
            return 1
        d = runs[-1]
        shots = sorted(p for p in d.glob("*.png") if p.stem.isdigit())
        if args.frame:
            shots = [p for p in shots if p.stem == args.frame]
    else:
        print("[ERR] 需要 --shot 或 --scene")
        return 1
    if not shots:
        print("[ERR] 没找到截图")
        return 1

    print(f"导出图 {len(pngs)} 张 × 截图 {len(shots)} 张\n")

    total = 0
    perfect = 0
    for png in pngs:
        tpl, alpha = load_png(png)
        best_all = None
        for shot_p in shots:
            shot = np.asarray(Image.open(shot_p).convert("RGB"))
            # 正向搜（导出图 ≤ 屏幕）；放不下就反着搜（屏幕 ≤ 导出图）
            fwd = match_template(shot, tpl, alpha)
            if fwd:
                r, x, y = fwd[0]
                cand = (r, x, y, shot_p.name, len(fwd), "fwd")
            else:
                rev = match_reverse(tpl, shot, alpha)
                if not rev:
                    continue
                r, x, y = rev[0]
                cand = (r, x, y, shot_p.name, len(rev), "rev")
            if best_all is None or cand[0] > best_all[0]:
                best_all = cand
        total += 1
        if best_all is None:
            print(f"  [MISS] {png.name}: 所有截图里都没找到（一致率 <50%）")
            continue
        r, x, y, shot_name, nhit, how = best_all
        tag = "EXACT" if r >= 0.999 else ("HIGH " if r >= 0.95 else "LOW  ")
        if r >= 0.999:
            perfect += 1
        where = "屏幕内" if how == "fwd" else "导出图内"
        print(f"  [{tag}] {png.name}: {r:.2%} @ {where}({x},{y}) vs {shot_name} "
              f"（{nhit} 处命中 >50%）")

    print(f"\n{'='*60}")
    print(f"精确匹配 {perfect}/{total} 张")
    return 0 if perfect == total else 2


if __name__ == "__main__":
    raise SystemExit(main())
