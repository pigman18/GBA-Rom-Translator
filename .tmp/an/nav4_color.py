# -*- coding: utf-8 -*-
"""分开颜色 dump：蓝墨 = #，红 = R，其他 = ?，看清蓝色文字的真实形态。"""
import numpy as np
from collections import Counter
a = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\shot_native.npy").astype(int)

# 全屏颜色统计
flat = a.reshape(-1, 3)
cnt = Counter(map(tuple, flat))
print("=== 全屏颜色 top 12 ===")
for c, n in cnt.most_common(12):
    print("  RGB%-18s x%d" % (str(c), n))

def kind(p):
    r, g, b = int(p[0]), int(p[1]), int(p[2])
    if (r, g, b) == (255, 255, 255): return '.'
    if abs(r-33)+abs(g-132)+abs(b-255) < 120: return '#'      # 蓝墨
    if r > 150 and g < 110 and b < 110: return 'R'            # 红
    if r > 200 and g > 200 and b > 200: return '.'            # 近白
    return '?'

def dump(x0, x1, y0, y1, title):
    print("\n" + "=" * 90)
    print(title)
    print("     " + "".join(str(x % 10) for x in range(x0, x1)))
    for y in range(y0, y1):
        print("%4d " % y + "".join(kind(a[y, x]) for x in range(x0, x1)))

dump(8, 56, 22, 40, "蓝墨文字？ x=8..55, y=22..39")
dump(8, 56, 40, 56, "第二行 x=8..55, y=40..55")

# 蓝墨的总分布
blue = np.zeros((160, 240), bool)
for y in range(160):
    for x in range(240):
        blue[y, x] = kind(a[y, x]) == '#'
print("\n蓝墨像素总数:", blue.sum())
rows = np.nonzero(blue.any(axis=1))[0]
print("蓝墨行范围:", rows.min(), rows.max())
# 每行蓝墨的列
print("\n=== 每行蓝墨列 ===")
for y in range(rows.min(), rows.max() + 1):
    cs = np.nonzero(blue[y])[0]
    if len(cs) == 0:
        print("%4d  (空)" % y); continue
    segs = []; s = cs[0]; p = cs[0]
    for c in cs[1:]:
        if c == p + 1: p = c
        else: segs.append((s, p)); s = c; p = c
    segs.append((s, p))
    print("%4d  n=%3d  %s" % (y, len(cs),
          " ".join("%d-%d" % t if t[0] != t[1] else "%d" % t[0] for t in segs)))
