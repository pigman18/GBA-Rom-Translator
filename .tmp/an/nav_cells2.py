"""nav_cells2.py — 按行带切 8x16 字格，逐格 ASCII。只读。"""
import numpy as np

g = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\nav_game.npy").astype(np.int32)
WHITE = np.array([255, 255, 255])
LINE_BANDS = {"A 标题": (8, 24), "B 第一列行": (24, 40), "C 第二列行": (40, 56)}


def cell_art(m, x0, y0, w=8, h=16):
    rows = []
    for r in range(h):
        rows.append("".join("#" if m[y0 + r, x0 + c] else "." for c in range(w)))
    return rows


for label, (y0, y1) in LINE_BANDS.items():
    band = g[y0:y1, 0:240]
    m = (np.abs(band - WHITE).sum(2) > 60)
    colsum = m.sum(0)
    xs = np.where(colsum > 0)[0]
    print(f"\n================ {label}  y{y0}..{y1-1}  墨水列范围 x {xs.min()}..{xs.max()} ================")
    # 以 x=%8 对齐的格起点
    start = (xs.min() // 8) * 8
    ncell = (xs.max() - start) // 8 + 1
    print(f"  格起点 x={start}  共 {ncell} 格")
    # 每个格的非零像素数
    for i in range(ncell):
        x0 = start + i * 8
        cnt = int(m[:, x0:x0 + 8].sum())
        print(f"    cell{i:2d} x={x0:3d} 墨={cnt:3d}")
    # 逐格 ASCII（横向并排打印 4 格一块）
    for blk in range(0, ncell, 4):
        print(f"\n  ---- 格 {blk}..{min(blk+3, ncell-1)} ----")
        arts = [cell_art(m, start + (blk + k) * 8, 0) for k in range(4) if blk + k < ncell]
        for r in range(16):
            print("   ", " | ".join(a[r] for a in arts))
