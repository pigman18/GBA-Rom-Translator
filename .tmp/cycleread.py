# -*- coding: utf-8 -*-
"""cycleread.py <tag> -- 把周期块当「一行文字」渲染出来，直接读字。"""
import os
import struct
import sys
from PIL import Image

T = r"C:\code\GBA-Rom-Translator\.tmp"


def rgb555(w):
    return ((w & 31) * 255 // 31, ((w >> 5) & 31) * 255 // 31, ((w >> 10) & 31) * 255 // 31)


tag = sys.argv[1]
lo = int(sys.argv[2])
n = int(sys.argv[3])       # 周期长度（砖）
SC = 8
v = open(os.path.join(T, "drive_%s_vram.bin" % tag), "rb").read()
io = open(os.path.join(T, "drive_%s_io.bin" % tag), "rb").read()
palb = open(os.path.join(T, "drive_%s_pal.bin" % tag), "rb").read()
cnt = struct.unpack_from("<H", io, 0x08)[0]
cbase = ((cnt >> 2) & 3) * 0x4000


def banks():
    return [[rgb555(struct.unpack_from("<H", palb, (b * 16 + i) * 2)[0]) for i in range(16)]
            for b in range(16)]


B = banks()
# 每个「map 列」占 2 砖（上/下）；周期 n 砖 = n/2 列
cols = n // 2
im = Image.new("RGB", (cols * 8 * SC, 16 * SC), (0, 0, 255))
for c in range(cols):
    for half in (0, 1):
        t = lo + c * 2 + half
        off = cbase + t * 32
        for y in range(8):
            for x in range(8):
                b = v[off + y * 4 + x // 2]
                idx = (b & 0xF) if x % 2 == 0 else (b >> 4)
                col = B[9][idx]
                for dy in range(SC):
                    for dx in range(SC):
                        # 上半放 0..7 行，下半放 8..15 行
                        py = (half * 8 + y) * SC + dy
                        px = c * 8 * SC + x * SC + dx
                        im.putpixel((px, py), col)
out = os.path.join(T, "cycle_%s_%d_%d.png" % (tag, lo, n))
im.save(out)
print("saved", out, im.size, "cols=%d" % cols)
