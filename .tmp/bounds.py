# -*- coding: utf-8 -*-
"""bounds.py <png...> — 自动找 GBA 屏幕区（对每行/列统计颜色数，取内容最丰富的矩形）"""
import sys
from collections import Counter
from PIL import Image
from pathlib import Path
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
for name in sys.argv[1:]:
    im = Image.open(T / name).convert("RGB")
    w, h = im.size
    px = im.load()
    # 每行/列的唯一色数
    rows = [len(set(px[x, y] for x in range(w))) for y in range(h)]
    cols = [len(set(px[x, y] for y in range(h))) for x in range(w)]
    def span(v, thr):
        idx = [i for i, n in enumerate(v) if n > thr]
        return (idx[0], idx[-1]) if idx else (0, 0)
    ys = span(rows, 6); xs = span(cols, 6)
    print("%s %dx%d  rows>6: %s  cols>6: %s  => 宽%d 高%d"
          % (name, w, h, ys, xs, xs[1]-xs[0]+1, ys[1]-ys[0]+1))
    # 该区域四角色
    print("     角: %s %s" % (px[xs[0], ys[0]], px[xs[1], ys[1]]))
