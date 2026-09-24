# -*- coding: utf-8 -*-
"""scr.py — 在 mgba_drive 截图里定位 240x160 画面矩形。

mGBA Qt 窗口截图带着标题栏 / 菜单栏 / 边框。画面本身是唯一一块
「宽 240*k、高 160*k」的内容区。做法：先在 x=W/2 列上找连续的非窗口底色
区段（窗口底色取四角像素），再在 y=H/2 行上做同样的事，两者交叉即为画面。

用法: python .tmp/scr.py <png> [--expect-rows N]
"""
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(r"C:/code/GBA-Rom-Translator")


def main():
    im = Image.open(sys.argv[1]).convert("RGB")
    W, H = im.size
    px = im.load()
    bg = px[2, H - 3]          # 左下角 = 窗口底色
    # 非底色 = 画面候选
    xs, ys = [], []
    for x in range(W):
        if px[x, H // 2] != bg:
            xs.append(x)
    for y in range(H):
        if px[W // 2, y] != bg:
            ys.append(y)
    # 取最长连续段
    def longest(v):
        best = (0, 0, 0)
        s = v[0]
        for i in range(1, len(v)):
            if v[i] != v[i - 1] + 1:
                if v[i - 1] - s + 1 > best[1] - best[0]:
                    best = (s, v[i - 1] + 1, v[i - 1] - s + 1)
                s = v[i]
        if v[-1] - s + 1 > best[1] - best[0]:
            best = (s, v[-1] + 1, v[-1] - s + 1)
        return best
    x0, x1, w = longest(xs)
    y0, y1, h = longest(ys)
    print("img %dx%d  bg=%s" % (W, H, bg))
    print("画面矩形 x[%d,%d) w=%d   y[%d,%d) h=%d   w/h=%.4f"
          % (x0, x1, w, y0, y1, h, w / float(h)))
    print("→ 缩放 k = %.3f (期望 3.000, 240x160)" % (w / 240.0))
    print("→ 用: x0=%d y0=%d k=%.3f" % (x0, y0, w / 240.0))


if __name__ == "__main__":
    main()
