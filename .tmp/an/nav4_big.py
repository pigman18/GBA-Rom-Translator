# -*- coding: utf-8 -*-
"""把截图文本带做成高清放大图（每像素 9x9 + 网格 + 绝对坐标），供肉眼确认。"""
import numpy as np
from PIL import Image, ImageDraw

a = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\shot_native.npy")
INK = np.array([33, 132, 255]); WHT = np.array([255, 255, 255])

Y0, Y1 = 20, 56          # 文本带
X0, X1 = 0, 240
Z = 9                    # 每像素放大倍数
sub = a[Y0:Y1, X0:X1]
h, w = sub.shape[:2]
pad_l, pad_t = 46, 22
img = Image.new("RGB", (pad_l + w * Z, pad_t + h * Z), (24, 24, 28))
d = ImageDraw.Draw(img)
for y in range(h):
    for x in range(w):
        c = tuple(int(v) for v in sub[y, x])
        d.rectangle([pad_l + x * Z, pad_t + y * Z,
                     pad_l + (x + 1) * Z - 1, pad_t + (y + 1) * Z - 1], fill=c)
# 网格：每像素细线，每 8 像素粗线
for x in range(w + 1):
    X = pad_l + x * Z
    col = (255, 120, 0) if (x + X0) % 8 == 0 else (70, 70, 80)
    d.line([X, pad_t, X, pad_t + h * Z], fill=col, width=2 if (x + X0) % 8 == 0 else 1)
for y in range(h + 1):
    Y = pad_t + y * Z
    col = (255, 120, 0) if (y + Y0) % 8 == 0 else (70, 70, 80)
    d.line([pad_l, Y, pad_l + w * Z, Y], fill=col, width=2 if (y + Y0) % 8 == 0 else 1)
# 坐标标注
for x in range(0, w, 8):
    d.text((pad_l + x * Z + 2, 4), str(x + X0), fill=(255, 220, 120))
for y in range(0, h, 4):
    d.text((4, pad_t + y * Z + 2), str(y + Y0), fill=(255, 220, 120))
img.save(r"C:\code\GBA-Rom-Translator\.tmp\an\nav4_band.png")
print("saved nav4_band.png", img.size)

# 只放大前 64px（第一个字附近）
for tag, xa, xb in (("A", 8, 72), ("B", 72, 136), ("C", 128, 192), ("D", 184, 240)):
    s = a[Y0:Y1, xa:xb]
    hh, ww = s.shape[:2]
    im = Image.new("RGB", (pad_l + ww * Z, pad_t + hh * Z), (24, 24, 28))
    dd = ImageDraw.Draw(im)
    for y in range(hh):
        for x in range(ww):
            dd.rectangle([pad_l + x * Z, pad_t + y * Z,
                          pad_l + (x + 1) * Z - 1, pad_t + (y + 1) * Z - 1],
                         fill=tuple(int(v) for v in s[y, x]))
    for x in range(ww + 1):
        X = pad_l + x * Z
        dd.line([X, pad_t, X, pad_t + hh * Z],
                fill=(255, 120, 0) if (x + xa) % 8 == 0 else (70, 70, 80),
                width=2 if (x + xa) % 8 == 0 else 1)
    for y in range(hh + 1):
        Y = pad_t + y * Z
        dd.line([pad_l, Y, pad_l + ww * Z, Y],
                fill=(255, 120, 0) if (y + Y0) % 8 == 0 else (70, 70, 80),
                width=2 if (y + Y0) % 8 == 0 else 1)
    for x in range(0, ww, 8):
        dd.text((pad_l + x * Z + 2, 4), str(x + xa), fill=(255, 220, 120))
    for y in range(0, hh, 2):
        dd.text((4, pad_t + y * Z + 2), str(y + Y0), fill=(255, 220, 120))
    im.save(r"C:\code\GBA-Rom-Translator\.tmp\an\nav4_%s.png" % tag)
    print("saved nav4_%s.png" % tag, im.size)
