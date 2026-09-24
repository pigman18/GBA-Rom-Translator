# -*- coding: utf-8 -*-
"""linechk.py <tag> -- 逐「文字行」把 dump 的 BG0 渲染成大图，供人眼判字。

一行文字 = map 相邻两行（R=R+1 是同一字模的下半）。同时把每个字的
tile 号序列打出来，便于和算法预测比对。
"""
import os
import struct
import sys
from PIL import Image

T = r"C:\code\GBA-Rom-Translator\.tmp"
SCALE = 4


def rgb555(w):
    return ((w & 31) * 255 // 31, ((w >> 5) & 31) * 255 // 31, ((w >> 10) & 31) * 255 // 31)


def load(tag):
    v = open(os.path.join(T, "drive_%s_vram.bin" % tag), "rb").read()
    io = open(os.path.join(T, "drive_%s_io.bin" % tag), "rb").read()
    pal = open(os.path.join(T, "drive_%s_pal.bin" % tag), "rb").read()
    return v, io, pal


tag = sys.argv[1]
v, io, palb = load(tag)
cnt = struct.unpack_from("<H", io, 0x08)[0]
hofs = struct.unpack_from("<H", io, 0x10)[0] & 0x1FF
vofs = struct.unpack_from("<H", io, 0x12)[0] & 0x1FF
cb, sb, size = (cnt >> 2) & 3, (cnt >> 8) & 0x1F, (cnt >> 14) & 3
w, h = {0: (32, 32), 1: (64, 32), 2: (32, 64), 3: (64, 64)}[size]
cbase, mbase = cb * 0x4000, sb * 0x800
print("cb%d sb%d sz%d hofs%d vofs%d" % (cb, sb, size, hofs, vofs))

# 16 个 BG bank × 16 色
banks = [[rgb555(struct.unpack_from("<H", palb, (b * 16 + i) * 2)[0]) for i in range(16)]
         for b in range(16)]

COLS = 28
ROWS = list(range(3, 18, 2))
lines = []
print("\n== 每行号序列（屏幕格）==")
for R in ROWS:
    cellw = []
    for c in range(COLS):
        sy, sx = R, c
        mx = (sx + hofs // 8) % w
        my = (sy + vofs // 8) % h
        e = struct.unpack_from("<H", v, mbase + (my * w + mx) * 2)[0]
        cellw.append((e & 0x3FF, (e >> 12) & 0xF))
    print("R%02d " % R + " ".join("%d/%d" % t for t in cellw))
    lines.append(cellw)

# 渲染：每行两格高（R, R+1），COLS 格宽
im = Image.new("RGB", (COLS * 8 * SCALE, len(ROWS) * 16 * SCALE + len(ROWS) * 6 * SCALE),
               (24, 24, 30))
y0 = 0
for li, R in enumerate(ROWS):
    for dy in (0, 1):
        sy = R + dy
        for c in range(COLS):
            mx = (c + hofs // 8) % w
            my = (sy + vofs // 8) % h
            e = struct.unpack_from("<H", v, mbase + (my * w + mx) * 2)[0]
            t, pl = e & 0x3FF, (e >> 12) & 0xF
            off = cbase + t * 32
            for y in range(8):
                for x in range(8):
                    b = v[off + y * 4 + x // 2]
                    idx = (b & 0xF) if x % 2 == 0 else (b >> 4)
                    col = banks[pl][idx]
                    for sdy in range(SCALE):
                        for sdx in range(SCALE):
                            im.putpixel((c * 8 * SCALE + x * SCALE + sdx,
                                         y0 + dy * 8 * SCALE + y * SCALE + sdy), col)
    y0 += 16 * SCALE + 6 * SCALE
out = os.path.join(T, "lines_%s.png" % tag)
im.save(out)
print("\nsaved", out, im.size)
