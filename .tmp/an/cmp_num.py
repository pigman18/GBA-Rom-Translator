# -*- coding: utf-8 -*-
"""对比：官方渲染的数字（基准） vs 我们画的中文。"""
import numpy as np
from PIL import Image

SHOT = r"C:\Users\Administrator\.workbuddy\clipboard-images\clipboard-2026-09-22T08-34-54-307Z-4d6b3feb.png"
a = np.array(Image.open(SHOT).convert("RGB"))
g = a[54:214, 1:241]

WHITE = np.array([255, 255, 255]); BLUE = np.array([0x21, 0x84, 0xFF])
d_w = np.abs(g.astype(np.int16) - WHITE).sum(axis=2)
d_b = np.abs(g.astype(np.int16) - BLUE).sum(axis=2)
ink = (d_b <= 60) & (d_b < d_w)

def dump(y0, y1, x0, x1, title):
    print("\n### %s  y=%d..%d x=%d..%d" % (title, y0, y1 - 1, x0, x1 - 1))
    print("      " + "".join(str(x // 10 % 10) for x in range(x0, x1)))
    print("      " + "".join(str(x % 10) for x in range(x0, x1)))
    for y in range(y0, y1):
        print("  %3d %s" % (y, "".join("#" if ink[y, x] else "." for x in range(x0, x1))))

# 官方数字 "17:26"（band1 右侧）
dump(25, 38, 185, 226, "官方数字 17:26")
# 官方数字 "55"（band2 x=81..103）
dump(41, 54, 79, 106, "官方数字 55")
# 我们画的中文块（band1 x=16..31）
dump(25, 38, 14, 34, "我方中文块 A (band1 x16..31)")
