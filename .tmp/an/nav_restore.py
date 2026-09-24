"""nav_restore.py — 把 mGBA 截图还原成 240x160 原像素并逐格分析。只读。"""
import numpy as np
from PIL import Image

SRC = r"C:\Users\Administrator\.workbuddy\clipboard-images\clipboard-2026-09-22T08-09-07-691Z-95ff2422.png"
OUT = r"C:\code\GBA-Rom-Translator\.tmp\an"

A = np.asarray(Image.open(SRC).convert("RGB")).astype(np.int32)
H, W, _ = A.shape
s = 3
nh, nw = 160 * s, 240 * s

best = None
for y0 in range(0, H - nh + 1):
    for x0 in range(0, W - nw + 1):
        sub = A[y0:y0 + nh, x0:x0 + nw].reshape(160, s, 240, s, 3)
        ref = sub[:, 0:1, :, 0:1, :]
        un = float((np.abs(sub - ref).sum(axis=4) == 0).mean())
        if best is None or un > best[0]:
            best = (un, x0, y0)
un, x0, y0 = best
print("=> 视口:", (x0, y0), "uniformity", round(un, 4))
g = A[y0:y0 + nh, x0:x0 + nw].reshape(160, s, 240, s, 3)[:, 0, :, 0, :]
np.save(f"{OUT}\\nav_game.npy", g.astype(np.uint8))
Image.fromarray(g.astype(np.uint8)).resize((240 * 4, 160 * 4), Image.NEAREST).save(f"{OUT}\\nav_game_x4.png")
print("saved nav_game_x4.png / nav_game.npy")

flat = g.reshape(-1, 3)
cols, cnts = np.unique(flat, axis=0, return_counts=True)
o = np.argsort(-cnts)[:14]
print("== 视口内 Top14 颜色 ==")
for i in o:
    print("   ", tuple(int(v) for v in cols[i]), int(cnts[i]))

# 判定"文字色"：非白、非灰、非红边的像素
mask = ~((np.abs(g - np.array([255, 255, 255])).sum(2) < 30)
          | (np.abs(g - np.array([144, 143, 143])).sum(2) < 40))
ys, xs = np.where(mask)
print("非白非灰像素 bbox: x", xs.min(), xs.max(), " y", ys.min(), ys.max())
