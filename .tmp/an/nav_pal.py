import numpy as np
from PIL import Image
from collections import Counter

im = Image.open(r"C:/Users/Administrator/.workbuddy/clipboard-images/clipboard-2026-09-22T08-09-07-691Z-95ff2422.png").convert("RGB")
a = np.array(im)
sc, ox, oy = 3, 1, 54
game = a[oy:oy+160*sc, ox:ox+240*sc].reshape(160, sc, 240, sc, 3).mean(axis=(1,3)).round().astype(int)

c = Counter(map(tuple, game.reshape(-1,3)))
print("top colors:")
for col, n in c.most_common(20):
    print(f"  {col}  {n}")

# 保存 4x 放大整屏
big = np.repeat(np.repeat(game.astype(np.uint8), 4, axis=0), 4, axis=1)
Image.fromarray(big).save(r"C:/code/GBA-Rom-Translator/.tmp/an/nav_game_x4b.png")
print("saved nav_game_x4b.png", big.shape)

# 裁剪左上角字形块（game 坐标 rows 24..60, x 8..72）放大 10x
crop = game[22:62, 8:72].astype(np.uint8)
big2 = np.repeat(np.repeat(crop, 10, axis=0), 10, axis=1)
Image.fromarray(big2).save(r"C:/code/GBA-Rom-Translator/.tmp/an/nav_crop1_x10.png")
print("saved nav_crop1_x10.png", big2.shape)

# 裁剪右下「17:26」区
crop2 = game[38:80, 170:240].astype(np.uint8)
big3 = np.repeat(np.repeat(crop2, 10, axis=0), 10, axis=1)
Image.fromarray(big3).save(r"C:/code/GBA-Rom-Translator/.tmp/an/nav_crop2_x10.png")
print("saved nav_crop2_x10.png", big3.shape)
