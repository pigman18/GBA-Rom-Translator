# -*- coding: utf-8 -*-
"""shot_view.py - 把 mGBA 截图缩到 GBA 原生 240x160 并按亮度打成 ASCII，
  让纯文本模型能"看"到画面。用法： python shot_view.py <png> [x0 y0 x1 y1]
"""
from __future__ import annotations
import sys
import os

import numpy as np
from PIL import Image

RAMP = " .:-=+*#%@"

def main():
    p = sys.argv[1]
    im = Image.open(p).convert("RGB")
    w, h = im.size
    # mGBA 截图有边框；先按比例缩到接近 240x160 的内容区
    scale = min(240.0 / w, 160.0 / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32)
    lum = (a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114) / 255.0
    if len(sys.argv) >= 6:
        x0, y0, x1, y1 = (int(v) for v in sys.argv[2:6])
        lum = lum[y0:y1, x0:x1]
    # 每个字符代表 1 个 GBA 像素；横向再 x2 因为字符比像素高
    chars = []
    for row in range(0, lum.shape[0], 1):
        line = []
        for col in range(0, lum.shape[1], 1):
            v = lum[row, col]
            line.append(RAMP[min(int(v * (len(RAMP) - 1) * 1.6), len(RAMP) - 1)])
        chars.append("".join(line))
    print("file=%s  native=%dx%d  crop=%s" % (os.path.basename(p), nw, nh,
                                              lum.shape[::-1] if lum.ndim == 2 else ""))
    for ln in chars:
        print(ln)

if __name__ == "__main__":
    main()
