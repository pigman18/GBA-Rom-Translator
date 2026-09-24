import numpy as np
from PIL import Image

P = r"C:\Users\Administrator\.workbuddy\clipboard-images\clipboard-2026-09-22T08-34-54-307Z-4d6b3feb.png"
a = np.array(Image.open(P).convert("RGB")).astype(int)

g = a[54:214, 1:241]          # 原生 240x160
np.save(r"C:\code\GBA-Rom-Translator\.tmp\an\nav3.npy", g)
print("viewport", g.shape)

# 墨色 = 蓝 (33,132,255)
ink = (np.abs(g - np.array([33,132,255])).sum(axis=2) < 40)
print("ink px total", ink.sum())

rows = np.where(ink.any(axis=1))[0]
cols = np.where(ink.any(axis=0))[0]
print("ink rows", rows.min(), rows.max())
print("ink cols", cols.min(), cols.max())

# 每行墨量
print("--- ink per row (nonzero) ---")
for y in range(g.shape[0]):
    n = ink[y].sum()
    if n:
        xs = np.where(ink[y])[0]
        print("y=%3d n=%3d  x=%d..%d" % (y, n, xs.min(), xs.max()))

# 放大输出
def zoom(y0, y1, x0, x1, f, name):
    sub = g[y0:y1, x0:x1]
    im = Image.fromarray(sub.astype(np.uint8)).resize(
        ((x1-x0)*f, (y1-y0)*f), Image.NEAREST)
    im.save(r"C:\code\GBA-Rom-Translator\.tmp\an\%s" % name)
    print("saved", name, sub.shape)

zoom(18, 56, 0, 240, 4, "nav3_top_x4.png")
zoom(0, 160, 0, 240, 3, "nav3_full_x3.png")
