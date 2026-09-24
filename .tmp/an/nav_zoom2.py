import numpy as np, sys
from PIL import Image

im = Image.open(r"C:/Users/Administrator/.workbuddy/clipboard-images/clipboard-2026-09-22T08-09-07-691Z-95ff2422.png").convert("RGB")
a = np.array(im)
print("screenshot", a.shape)

# 游戏视口：prev 轮已定 scale=3, origin=(1,54)
sc, ox, oy = 3, 1, 54
g = a[oy:oy+160*sc, ox:ox+240*sc]
# 逐像素降采样（整除校验）
H, W, _ = g.shape
g = g[:160*sc, :240*sc]
game = g.reshape(160, sc, 240, sc, 3).mean(axis=(1,3))
print("game", game.shape)

# 找出「蓝字」掩码：蓝通道高、红通道低
r, gg, b = game[:,:,0], game[:,:,1], game[:,:,2]
ink = (b > 120) & (r < 140)
white = (r > 200) & (gg > 200) & (b > 200)
print("ink px", int(ink.sum()), "white px", int(white.sum()))

# 每行的墨量
rows = ink.sum(axis=1)
for y in range(160):
    if rows[y] or rows[y-1] if y else rows[y]:
        pass
print("row ink profile (only nonzero):")
for y in range(160):
    if rows[y] > 0:
        print(f"  y={y:3d} ink={rows[y]:3d}")
