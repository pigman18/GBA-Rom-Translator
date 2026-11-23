"""对比 origin/translated PNG，输出差异包围盒，并按 tile 分块统计。

用法: python scripts/image/png_diff.py <run_dir> <frame>
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

RUN = Path(sys.argv[1])
FRAME = sys.argv[2]


def main():
    o = np.array(Image.open(RUN / "origin" / f"{FRAME}.png").convert("RGB")).astype(int)
    t = np.array(Image.open(RUN / "translated" / f"{FRAME}.png").convert("RGB")).astype(int)
    print(f"size origin={o.shape} translated={t.shape}")
    d = (np.abs(o - t).sum(axis=2) > 0)
    ys, xs = np.nonzero(d)
    print(f"差异像素 {d.sum()}  包围盒 x=[{xs.min()},{xs.max()}] y=[{ys.min()},{ys.max()}]")

    # 按 8x8 tile 分块
    h, w = d.shape
    print("\n差异 tile (8x8 像素格，含差异像素数):")
    rows = []
    for ty in range(0, h, 8):
        line = []
        for tx in range(0, w, 8):
            c = int(d[ty:ty + 8, tx:tx + 8].sum())
            line.append(f"{c:3d}" if c else "  .")
        rows.append((ty, line))
    for ty, line in rows:
        if any(x.strip() != "." for x in line):
            print(f" y={ty:3d}: " + " ".join(line))

    # 逐行统计差异像素
    print("\n按扫描行统计差异（仅非零行）:")
    for y in range(h):
        c = int(d[y].sum())
        if c:
            xs_y = np.nonzero(d[y])[0]
            print(f"  y={y:3d}: {c:3d} px  x=[{xs_y.min()},{xs_y.max()}]")


if __name__ == "__main__":
    main()
