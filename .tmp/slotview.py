# -*- coding: utf-8 -*-
"""slotview.py <tag> <t0> [n] — 把连续 n 个槽（每槽 4 砖 [左上,左下,右上,右下]）
   渲染成 16x16 灰度图，横向拼一条。0=白底, 15=黑；也打印每砖非零值集合。"""
import sys
from pathlib import Path
from PIL import Image
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag = sys.argv[1]
t0 = int(sys.argv[2])
n = int(sys.argv[3]) if len(sys.argv) > 3 else 1
# 基址：cb1 窗口 tdata=0x06004000；用 0x06004000 作块基址 + t0
blk = 0x06004000
if len(sys.argv) > 4:
    blk = int(sys.argv[4], 16)
v = (T / ("drive_%s_vram.bin" % tag)).read_bytes()


def tile(t):
    off = blk + t * 32 - 0x06000000
    return v[off:off + 32]


img = Image.new("L", (n * 16 + (n - 1) * 2, 16), 128)
for k in range(n):
    a, b, c, d = (tile(t0 + k * 4 + i) for i in range(4))
    px = [[255] * 16 for _ in range(16)]
    vals = set()
    for quadrant, (tl, rows) in enumerate(((a, range(0, 8)), (b, range(8, 16)),
                                           (c, range(0, 8)), (d, range(8, 16)))):
        for ri, ry in enumerate(rows):
            row = tl[ri * 4:ri * 4 + 4]
            for ci in range(8):
                byte = row[ci // 2]
                val = (byte & 0xF) if ci % 2 == 0 else (byte >> 4)
                vals.add(val)
                x = ci + (8 if quadrant in (2, 3) else 0)
                px[ry][x] = 255 - val * 17
    for y in range(16):
        for x in range(16):
            img.putpixel((k * 18 + x, y), px[y][x])
    print("槽%d t0=%d 值集合=%s" % (k, t0 + k * 4, sorted(vals)))
img = img.resize((img.width * 6, img.height * 6), Image.NEAREST)
img.save(T / ("slotview_%s_%d.png" % (tag, t0)))
print(T / ("slotview_%s_%d.png" % (tag, t0)), img.size)
