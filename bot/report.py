#!/usr/bin/env python3
"""bot/report.py — 全屏对照报告（不看裁剪块，只看整屏）

用户口径：验收必须先看**整屏**，小裁图会漏掉「一眼就能看见」的错位/糊屏。

输出
----
  work/{gameId}/bot/{scene}/{stamp}/report_full.png
      每帧一行三列：origin 全屏 | translated 全屏 | 差异图（红=新增/蓝=丢失）
      2 倍放大、每帧 48px 标注，整屏 240×160 完整可见。

  stdout 表格：每帧 差异px / 差异bbox / 连通块(≥6px) 数 / 最大块 / 判定提示

用法
----
  python bot/report.py <run_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SCALE = 2
LABEL_H = 18
GAP = 6


def font(size=12):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/consola.ttf", size)
    except Exception:
        return ImageFont.load_default()


def load(p: Path) -> np.ndarray:
    return np.asarray(Image.open(p).convert("RGB")).astype(np.int16)


def components(mask: np.ndarray, min_px: int = 6):
    """8 邻接连通块（小图，BFS 足够）。"""
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]
        seen[y0, x0] = True
        pts = []
        while stack:
            y, x = stack.pop()
            pts.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        if len(pts) >= min_px:
            ys_ = [p[0] for p in pts]
            xs_ = [p[1] for p in pts]
            out.append((len(pts), min(xs_), min(ys_), max(xs_), max(ys_)))
    out.sort(reverse=True)
    return out


def diff_image(o: np.ndarray, t: np.ndarray) -> np.ndarray:
    d = np.abs(o - t).sum(axis=2) > 12
    img = np.zeros((o.shape[0], o.shape[1], 3), dtype=np.uint8)
    img[..., 0] = np.where(d, 255, 0)          # 差异：红
    img[..., 1] = (o.mean(axis=2) // 3).astype(np.uint8)
    img[..., 2] = np.where(d, 0, 40)
    return img


def label(draw, xy, text, fill=(255, 255, 255)):
    draw.text(xy, text, font=font(12), fill=fill)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    run = Path(sys.argv[1])
    o_dir, t_dir = run / "origin", run / "translated"
    if not o_dir.is_dir():
        print(f"[ERR] 没有 origin/ 目录: {run}")
        return 2

    pairs = sorted(p.name for p in o_dir.glob("*.png"))
    pairs = [p for p in pairs if (t_dir / p).is_file()]
    if not pairs:
        print("[ERR] 没有可对照的帧")
        return 2

    W, H = 240, 160
    cell_w = W * SCALE
    row_h = H * SCALE + LABEL_H
    cols = 3
    sheet_w = cols * cell_w + (cols + 1) * GAP
    sheet_h = len(pairs) * (row_h + GAP) + GAP
    sheet = Image.new("RGB", (sheet_w, sheet_h), (18, 18, 20))
    draw = ImageDraw.Draw(sheet)

    print(f"{'帧':<16}{'差异px':>8}{'差异bbox':>26}{'块≥6':>6}{'最大块':>8}  备注")
    print("-" * 96)

    for i, name in enumerate(pairs):
        o = load(o_dir / name)
        t = load(t_dir / name)
        if o.shape != t.shape:
            print(f"{name}: 尺寸不一致 {o.shape} vs {t.shape}")
            continue
        d = np.abs(o - t).sum(axis=2) > 12
        n = int(d.sum())
        ys, xs = np.nonzero(d)
        bbox = "-" if n == 0 else f"({xs.min()},{ys.min()})-({xs.max()},{ys.max()})"
        comps = components(d, 6)
        biggest = f"{comps[0][0]}px@({comps[0][1]},{comps[0][2]})" if comps else "-"
        note = ""
        if n == 0:
            note = "两侧一致（可能本帧无文字）"
        elif comps and comps[0][0] > 120:
            note = "★大块差异，需人眼确认"
        print(f"{name:<16}{n:>8}{bbox:>26}{len(comps):>6}{biggest:>10}  {note}")

        y = GAP + i * (row_h + GAP)
        for c, (img, title) in enumerate((
            (o.astype(np.uint8), "origin"),
            (t.astype(np.uint8), "translated"),
            (diff_image(o, t), "diff"),
        )):
            x = GAP + c * (cell_w + GAP)
            im = Image.fromarray(img).resize((cell_w, H * SCALE), Image.NEAREST)
            sheet.paste(im, (x, y + LABEL_H))
            label(draw, (x + 2, y + 2), f"{name}  {title}")

    out = run / "report_full.png"
    sheet.save(out)
    print(f"\n[saved] {out}  ({sheet_w}x{sheet_h}, 每帧三列：origin/translated/diff)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
