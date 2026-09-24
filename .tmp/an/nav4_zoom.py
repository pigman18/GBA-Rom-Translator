# -*- coding: utf-8 -*-
"""把截图原生视口放大到能逐像素看清，标出每像素网格与列号。"""
import numpy as np
from PIL import Image, ImageDraw

SH = r"C:\code\GBA-Rom-Translator\.tmp\an\shot_native.npy"
a = np.load(SH)                      # (160,240,3) 原生
print("shape", a.shape)

# 认墨：与蓝墨 (33,132,255) 距离近
INK = np.array([33, 132, 255])
WHT = np.array([255, 255, 255])
ink = (np.abs(a.astype(int) - INK).sum(axis=2) < 60)
print("总墨像素", ink.sum())
rows = np.nonzero(ink.any(axis=1))[0]
cols = np.nonzero(ink.any(axis=0))[0]
print("墨迹行 range", rows.min(), rows.max())
print("墨迹列 range", cols.min(), cols.max())

# 每行墨量
print("\n--- 逐行墨量 ---")
for y in range(rows.min(), rows.max() + 1):
    n = int(ink[y].sum())
    cs = np.nonzero(ink[y])[0]
    rng = ""
    if len(cs):
        # 压缩成区间
        segs = []
        s = cs[0]; p = cs[0]
        for c in cs[1:]:
            if c == p + 1:
                p = c
            else:
                segs.append((s, p)); s = c; p = c
        segs.append((s, p))
        rng = " ".join("%d-%d" % t if t[0] != t[1] else "%d" % t[0] for t in segs)
    print("%3d  n=%3d  %s" % (y, n, rng))
