# -*- coding: utf-8 -*-
"""精确定位截图里的 GBA 画面区（240x160），再分色 dump 文字。"""
import numpy as np
from PIL import Image

SHOT = r"C:\Users\Administrator\.workbuddy\clipboard-images\clipboard-2026-09-22T08-34-54-307Z-4d6b3feb.png"
OUT = r"C:\code\GBA-Rom-Translator\.tmp\an"

a = np.array(Image.open(SHOT).convert("RGB")).astype(np.int16)
print("shot:", a.shape)

# 画面外应该是 mGBA 的 UI 灰 + 底部大片紫灰。找"红色边框"首行。
red = ((a[:, :, 0] > 100) & (a[:, :, 1] < 90) & (a[:, :, 2] < 90))
rows_red = red.sum(axis=1)
print("\nrows with red-pixels (first 200):")
print(" ".join("%d:%d" % (i, v) for i, v in enumerate(rows_red) if v > 30))

# 每行主色（众数）
print("\nper-row mode colour:")
for y in range(0, a.shape[0], 1):
    row = a[y]
    cols, cnts = np.unique(row, axis=0, return_counts=True)
    m = cols[np.argmax(cnts)]
    if y < 60 or y > 180:
        print("  y=%3d  #%02X%02X%02X  (n=%d)" % (
            y, int(m[0]), int(m[1]), int(m[2]), int(cnts.max())))
