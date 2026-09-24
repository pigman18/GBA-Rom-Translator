"""nav_cells.py — 从还原后的 240x160 里抠字格，打印 ASCII，判定故障形态。只读。"""
import numpy as np
from PIL import Image

g = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\nav_game.npy").astype(np.int32)
print("g", g.shape)

WHITE = np.array([255, 255, 255])
GRAY = np.array([144, 143, 143])


def ink_of(x0, y0, w, h, bg):
    sub = g[y0:y0 + h, x0:x0 + w]
    return (np.abs(sub - bg).sum(2) > 60)


def show(x0, y0, w, h, bg, label):
    print(f"\n--- {label}  区 ({x0},{y0}) {w}x{h} ---")
    m = ink_of(x0, y0, w, h, bg)
    for r in range(h):
        print("   ", "".join("#" if m[r, c] else "." for c in range(w)))


# 1) 标题行（第 1 行，黑字，白底）
show(16, 8, 48, 16, WHITE, "标题行 前6格")
# 2) 第 2 行蓝字（第 1 列）
show(16, 32, 32, 16, WHITE, "第2行 第1列 4格")
# 3) 蓝字区域整行
show(16, 32, 96, 16, WHITE, "第2行 全 12格")

# 4) 精确颜色：标题行墨像素的颜色分布
sub = g[8:24, 16:64]
flat = sub.reshape(-1, 3)
cols, cnts = np.unique(flat, axis=0, return_counts=True)
o = np.argsort(-cnts)[:8]
print("\n== 标题区颜色 ==")
for i in o:
    print("   ", tuple(int(v) for v in cols[i]), int(cnts[i]))

# 5) 蓝字区颜色
sub = g[32:48, 16:112]
flat = sub.reshape(-1, 3)
cols, cnts = np.unique(flat, axis=0, return_counts=True)
o = np.argsort(-cnts)[:8]
print("\n== 蓝字区颜色 ==")
for i in o:
    print("   ", tuple(int(v) for v in cols[i]), int(cnts[i]))

# 6) 灰框区颜色
sub = g[96:112, 16:64]
flat = sub.reshape(-1, 3)
cols, cnts = np.unique(flat, axis=0, return_counts=True)
o = np.argsort(-cnts)[:8]
print("\n== 灰框标题区颜色 ==")
for i in o:
    print("   ", tuple(int(v) for v in cols[i]), int(cnts[i]))
