import numpy as np
from PIL import Image

P = r"C:\Users\Administrator\.workbuddy\clipboard-images\clipboard-2026-09-22T08-34-54-307Z-4d6b3feb.png"
im = Image.open(P).convert("RGB")
a = np.array(im)
print("size", im.size, "shape", a.shape)

# 找游戏视口：mGBA 窗口，找连续非灰边框区
# 直接打印每行/列的主色变化
h, w, _ = a.shape
# 统计颜色
cols, cnt = np.unique(a.reshape(-1,3), axis=0, return_counts=True)
order = np.argsort(-cnt)
print("--- top colors ---")
for i in order[:12]:
    print(tuple(cols[i]), cnt[i])

# 找视口边界：mGBA 菜单栏下方
# 观察每行是否含窗口标题栏灰色
for y in range(0, min(h,80)):
    row = a[y]
    uniq = len(np.unique(row, axis=0))
    print("y=%3d uniq=%3d  first=%s mid=%s" % (y, uniq, tuple(row[0]), tuple(row[w//2])))
