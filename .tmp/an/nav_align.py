"""nav_align.py — 精确定位文本行带与 8x16 字格，逐格打印 ASCII + 与字库比对。只读。"""
import numpy as np

g = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\nav_game.npy").astype(np.int32)
WHITE = np.array([255, 255, 255])

# 白底区域：x 16..223, y 8..92（第 1 行标题 + 第 2/3 行）
sub = g[0:100, 0:240]
ink = (np.abs(sub - WHITE).sum(2) > 60)

print("== 逐行墨量 (y : count) [y 0..99] ==")
for y in range(0, 100):
    c = int(ink[y].sum())
    if c:
        print(f"   y={y:3d} {c:4d} " + "#" * min(60, c // 2))
