# -*- coding: utf-8 -*-
"""lineview.py <tag> <bg> -- 把该层所有「文字行」（map 奇偶行对）渲染成一张叠图，便于肉眼读屏。
按调色板索引着色：1=白(主墨) 2/3/4=灰 8=红 9=蓝 15=浅白 0=黑。"""
import struct
import sys
from pathlib import Path
from PIL import Image, ImageDraw

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
PAL = {0: (10, 10, 12), 1: (255, 255, 255), 2: (200, 200, 205), 3: (180, 180, 190),
       4: (160, 160, 170), 5: (140, 140, 150), 6: (120, 120, 130), 7: (100, 100, 110),
       8: (255, 60, 60), 9: (60, 180, 255), 10: (90, 240, 90), 11: (255, 210, 60),
       12: (215, 130, 255), 13: (255, 150, 50), 14: (130, 190, 255), 15: (235, 235, 235)}

tag, bg = sys.argv[1], int(sys.argv[2])
y0 = int(sys.argv[3]) if len(sys.argv) > 3 else 0
y1 = int(sys.argv[4]) if len(sys.argv) > 4 else 20
SC = int(sys.argv[5]) if len(sys.argv) > 5 else 3

v = (T / ("drive_%s_vram.bin" % tag)).read_bytes()
iod = (T / ("drive_%s_io.bin" % tag)).read_bytes()
disp = struct.unpack_from("<H", iod, 0)[0]
cnt = struct.unpack_from("<H", iod, 0x08 + 2 * bg)[0]
cb, sb, size = (cnt >> 2) & 3, (cnt >> 8) & 0x1F, (cnt >> 14) & 3
W = 32 if size in (0, 2) else 64
cbase, moff = cb * 0x4000, sb * 0x800

pairs = []
y = y0
while y + 1 < y1:
    used = [struct.unpack_from("<H", v, moff + (y * W + c) * 2)[0] & 0x3FF for c in range(W)]
    if any(t >= 521 for t in used):
        pairs.append(y)
        y += 2
    else:
        y += 1

CW, CH = W * 8 * SC, 16 * SC + 14
im = Image.new("RGB", (CW, len(pairs) * CH + 6), (25, 25, 30))
dr = ImageDraw.Draw(im)
for i, yy in enumerate(pairs):
    dr.text((2, 2 + i * CH), "map r%d" % yy, fill=(255, 255, 0))
    for c in range(W):
        for half in (0, 1):
            t = struct.unpack_from("<H", v, moff + ((yy + half) * W + c) * 2)[0] & 0x3FF
            o = cbase + t * 32
            for yv in range(8):
                for xv in range(8):
                    b = v[o + yv * 4 + xv // 2]
                    px = (b & 0xF) if xv % 2 == 0 else (b >> 4)
                    col = PAL.get(px, (255, 0, 255))
                    X0 = c * 8 * SC + xv * SC
                    Y0 = 6 + i * CH + (half * 8 + yv) * SC
                    for dy in range(SC):
                        for dx in range(SC):
                            im.putpixel((X0 + dx, Y0 + dy), col)
out = T / ("lines_%s_%s.png" % (tag, bg))
im.save(out)
print("saved", out, im.size, "rows:", pairs)
