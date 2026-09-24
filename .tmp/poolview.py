# -*- coding: utf-8 -*-
"""poolview.py <tag> <lo> <n> [rowpairs] -- 把池区 4bpp 砖铺成长条图（16 行高），带砖号刻度。"""
import struct
import sys
from pathlib import Path
from PIL import Image, ImageDraw

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag, lo, n = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
per_row = int(sys.argv[4]) if len(sys.argv) > 4 else 60      # 每行显示多少砖对(=2砖)
v = (T / f"drive_{tag}_vram.bin").read_bytes()
io = (T / f"drive_{tag}_io.bin").read_bytes()
cbase = ((struct.unpack_from("<H", io, 0x08)[0] >> 2) & 3) * 0x4000

SC = 8
GH = 16 * SC
rows = (n + per_row - 1) // per_row
W = per_row * 16 * SC
HDR = 16
im = Image.new("RGB", (W, rows * (GH + HDR) + HDR), (16, 16, 20))
dr = ImageDraw.Draw(im)
PAL = {0: (16, 16, 20), 1: (250, 250, 250), 2: (140, 140, 150), 3: (120, 120, 130),
       4: (110, 110, 120), 5: (100, 100, 110), 6: (95, 95, 105), 7: (90, 90, 100),
       8: (255, 80, 80), 9: (80, 200, 255), 10: (120, 255, 120), 11: (255, 220, 80),
       12: (220, 140, 255), 13: (255, 160, 60), 14: (140, 200, 255), 15: (230, 230, 230)}

for i in range(n):
    t = lo + 2 * i
    ry, rx = divmod(i, per_row)
    oy = HDR + ry * (GH + HDR)
    for half in (0, 1):
        off = cbase + (t + half) * 32
        for y in range(8):
            for x in range(8):
                b = v[off + y * 4 + x // 2]
                px = (b & 0xF) if x % 2 == 0 else (b >> 4)
                col = PAL.get(px, (200, 200, 200))
                for dy in range(SC):
                    for dx in range(SC):
                        im.putpixel((rx * 16 * SC + (half * 8 + x) * SC + dx,
                                     oy + y * SC + dy), col)
    if i % 5 == 0:
        X = rx * 16 * SC
        dr.line([(X, oy), (X, oy + GH)], fill=(90, 160, 90))
        dr.text((X + 2, oy + GH + 2), str(t), fill=(150, 255, 150))

dr.text((2, 2), "pool %d..%d tiles; green ticks = every 5 pairs; colors=palette index"
        % (lo, lo + 2 * n - 1), fill=(220, 220, 220))
out = T / ("poolview_%s_%d_%d.png" % (tag, lo, n))
im.save(out)
print("saved", out, im.size)
