# -*- coding: utf-8 -*-
"""重建整行文本：原始 / 抽偶列 / 抽奇列，放大成图供肉眼辨认。"""
import numpy as np
from PIL import Image, ImageDraw

a = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\shot_native.npy").astype(int)
blue = (np.abs(a - np.array([33, 132, 255])).sum(axis=2) < 60)

def strip(y0, x0, x1):
    return blue[y0:y0 + 11, x0:x1]

def add_grid(im, ox, oy, Z, w, h, every=8, xoff=0):
    d = ImageDraw.Draw(im)
    for x in range(w + 1):
        X = ox + x * Z
        c = (255, 120, 0) if (x + xoff) % every == 0 else (72, 72, 84)
        d.line([X, oy, X, oy + h * Z], fill=c, width=2 if (x + xoff) % every == 0 else 1)
    for y in range(h + 1):
        Y = oy + y * Z
        c = (255, 120, 0) if y % every == 0 else (72, 72, 84)
        d.line([ox, Y, ox + w * Z, Y], fill=c, width=2 if y % every == 0 else 1)

def paint(im, sx, sy, Z, mat):
    d = ImageDraw.Draw(im)
    for y in range(mat.shape[0]):
        for x in range(mat.shape[1]):
            d.rectangle([sx + x * Z, sy + y * Z, sx + (x + 1) * Z - 1, sy + (y + 1) * Z - 1],
                        fill=(40, 140, 255) if mat[y, x] else (245, 245, 250))

for tag, y0 in (("row1", 26), ("row2", 42)):
    S = strip(y0, 8, 152)                       # 144 x 11
    ev = S[:, 8::2]                             # 抽偶列（相对 x=8 起）
    od = S[:, 9::2]
    Z = 7
    W = S.shape[1]
    W2 = ev.shape[1]
    pad = 60
    im = Image.new("RGB", (pad + max(W, W2) * Z + 20, 40 + (11 * 3 + 24) * Z + 40), (24, 24, 28))
    d = ImageDraw.Draw(im)
    d.text((8, 8), "%s  y=%d..%d   original x=8..151" % (tag, y0, y0 + 10), fill=(255, 220, 120))
    paint(im, pad, 26, Z, S)
    add_grid(im, pad, 26, Z, W, 11, every=8, xoff=8)
    y2 = 26 + 11 * Z + 24
    d.text((8, y2 - 18), "even cols (x=8,10,...)  -> %d cols" % W2, fill=(255, 220, 120))
    paint(im, pad, y2, Z, ev)
    add_grid(im, pad, y2, Z, W2, 11, every=8, xoff=0)
    y3 = y2 + 11 * Z + 24
    d.text((8, y3 - 18), "odd cols (x=9,11,...)", fill=(255, 220, 120))
    paint(im, pad, y3, Z, od)
    add_grid(im, pad, y3, Z, W2, 11, every=8, xoff=0)
    out = r"C:\code\GBA-Rom-Translator\.tmp\an\nav4_%s.png" % tag
    im.save(out)
    print("saved", out, im.size)

    # ASCII 抽偶列（分块打印，每 8 列一组）
    print("\n=== %s 抽偶列，按 8 列分组 ===" % tag)
    for g in range(0, W2, 8):
        blk = ev[:, g:g + 8]
        if blk.sum() == 0: continue
        print("  -- cols %d..%d --" % (g, g + 7))
        for y in range(11):
            print("     " + "".join("#" if blk[y, x] else "." for x in range(blk.shape[1])))
