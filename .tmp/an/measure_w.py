# -*- coding: utf-8 -*-
"""精确测量屏幕上每个字符块的 x 边界与宽度（列投影 + 块切分）。"""
import numpy as np
from PIL import Image

SHOT = r"C:\Users\Administrator\.workbuddy\clipboard-images\clipboard-2026-09-22T08-34-54-307Z-4d6b3feb.png"
a = np.array(Image.open(SHOT).convert("RGB"))
g = a[54:214, 1:241]

WHITE = np.array([255, 255, 255])
BLUE = np.array([0x21, 0x84, 0xFF])
d_w = np.abs(g.astype(np.int16) - WHITE).sum(axis=2)
d_b = np.abs(g.astype(np.int16) - BLUE).sum(axis=2)
ink = (d_b <= 60) & (d_b < d_w)

for (y0, y1, tag) in ((25, 38, "band1"), (41, 54, "band2")):
    sub = ink[y0:y1]
    print("\n=== %s  y=%d..%d ===" % (tag, y0, y1 - 1))
    proj = sub.sum(axis=0)
    # 连续有墨段
    segs, s = [], None
    for x in range(240):
        if proj[x] > 0 and s is None:
            s = x
        elif proj[x] == 0 and s is not None:
            segs.append((s, x - 1)); s = None
    if s is not None:
        segs.append((s, 239))
    print("  ink segments (x0..x1, w):")
    for (s, e) in segs:
        print("    %3d..%3d  w=%2d  ink=%d" % (s, e, e - s + 1, proj[s:e + 1].sum()))
    # 每 8 列墨量
    print("  per-8col ink:", [int(proj[x:x + 8].sum()) for x in range(0, 240, 8)])
