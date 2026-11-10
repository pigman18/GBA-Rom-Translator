#!/usr/bin/env python3
"""实际对比 origin vs translated 的图像内容（不用 hash）。

判据：逐像素找出「变了的地方」，并输出变化区域，
      让人能直接看出「原版是什么字 → 汉化是什么字」。

用法：
    python scripts/research/ruby/img_diff_real.py <origin.png> <translated.png>
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main() -> int:
    if len(sys.argv) < 3:
        sys.exit("用法: img_diff_real.py <origin.png> <translated.png>")

    try:
        from PIL import Image
    except ImportError:
        sys.exit("需要 Pillow")

    a = Image.open(sys.argv[1]).convert("RGB")
    b = Image.open(sys.argv[2]).convert("RGB")
    if a.size != b.size:
        print(f"尺寸不同: {a.size} vs {b.size}")
        return 1

    w, h = a.size
    pa, pb = a.load(), b.load()

    # 逐像素差异
    diff_count = 0
    min_x = w
    max_x = -1
    min_y = h
    max_y = -1
    rows: dict[int, tuple[int, int]] = {}

    for y in range(h):
        row_lo, row_hi = w, -1
        for x in range(w):
            if pa[x, y] != pb[x, y]:
                diff_count += 1
                row_lo = min(row_lo, x)
                row_hi = max(row_hi, x)
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
        if row_hi >= 0:
            rows[y] = (row_lo, row_hi)

    print(f"图像 {w}×{h}")
    print(f"不同像素: {diff_count} / {w*h} ({diff_count/(w*h):.2%})")
    if max_x < 0:
        print("两图完全一致")
        return 0

    print(f"差异区域: x[{min_x},{max_x}] y[{min_y},{max_y}]")
    print()
    print("按行聚合（连续行合并成块）:")
    ys = sorted(rows)
    blocks = []
    cur = [ys[0]]
    for y in ys[1:]:
        if y == cur[-1] + 1:
            cur.append(y)
        else:
            blocks.append(cur)
            cur = [y]
    blocks.append(cur)

    for blk in blocks:
        y0, y1 = blk[0], blk[-1]
        x0 = min(rows[y][0] for y in blk)
        x1 = max(rows[y][1] for y in blk)
        npix = sum(1 for y in blk for x in range(w) if pa[x, y] != pb[x, y])
        print(f"  块 y[{y0},{y1}] x[{x0},{x1}]  像素 {npix}")

    # 保存差异可视化（差异处标红）
    vis = Image.new("RGB", (w, h))
    pv = vis.load()
    for y in range(h):
        for x in range(w):
            if pa[x, y] != pb[x, y]:
                pv[x, y] = (255, 0, 0)
            else:
                pv[x, y] = pb[x, y]
    outp = Path(sys.argv[2]).with_suffix(".diff.png")
    vis.save(outp)
    print(f"\n差异可视化 → {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
