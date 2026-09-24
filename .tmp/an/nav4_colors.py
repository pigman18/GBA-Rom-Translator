# -*- coding: utf-8 -*-
"""文本区的完整颜色分布 —— 检查"奇数列"是不是另一种颜色（= 发虚的真相）。"""
import numpy as np
from collections import Counter

a = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\shot_native.npy").astype(int)

REGIONS = [("中文文本区1 x16..143 y24..40", 16, 144, 24, 40),
           ("中文文本区2 x16..143 y40..56", 16, 144, 40, 56),
           ("官方数字区 x184..232 y24..40", 184, 232, 24, 40),
           ("空背景区 x150..184 y24..40", 150, 184, 24, 40)]

def lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]

for name, x0, x1, y0, y1 in REGIONS:
    sub = a[y0:y1, x0:x1].reshape(-1, 3)
    cnt = Counter(map(tuple, sub))
    print("\n=== %s  共 %d 像素, %d 种颜色 ===" % (name, len(sub), len(cnt)))
    for c, n in cnt.most_common(12):
        print("   RGB%-20s x%-6d  %5.2f%%" % (str(c), n, 100.0 * n / len(sub)))

# 逐列：文本区第一行，统计每列的颜色构成
print("\n=== 文本区1 逐列颜色（y=26..36）===")
for x in range(14, 48):
    col = a[26:37, x]
    cnt = Counter(map(tuple, col))
    top = cnt.most_common(3)
    print("  x=%3d  %s" % (x, "  ".join("%s x%d" % (str(c), n) for c, n in top)))
