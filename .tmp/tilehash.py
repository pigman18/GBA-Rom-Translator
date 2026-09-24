# -*- coding: utf-8 -*-
"""tilehash.py <tag> -- 把 dump 里各砖的内容做指纹分组，看「内容是否在循环/重复」。

同时把每块砖用真调色板渲染成小图，拼成一张带号标注的总表，便于判字。
"""
import os
import struct
import sys
from collections import defaultdict
from PIL import Image, ImageDraw

T = r"C:\code\GBA-Rom-Translator\.tmp"


def rgb555(w):
    return ((w & 31) * 255 // 31, ((w >> 5) & 31) * 255 // 31, ((w >> 10) & 31) * 255 // 31)


tag = sys.argv[1]
lo = int(sys.argv[2]) if len(sys.argv) > 2 else 521
hi = int(sys.argv[3]) if len(sys.argv) > 3 else 700
v = open(os.path.join(T, "drive_%s_vram.bin" % tag), "rb").read()
io = open(os.path.join(T, "drive_%s_io.bin" % tag), "rb").read()
palb = open(os.path.join(T, "drive_%s_pal.bin" % tag), "rb").read()
cnt = struct.unpack_from("<H", io, 0x08)[0]
cb = (cnt >> 2) & 3
cbase = cb * 0x4000
bank9 = [rgb555(struct.unpack_from("<H", palb, (9 * 16 + i) * 2)[0]) for i in range(16)]
bank8 = [rgb555(struct.unpack_from("<H", palb, (8 * 16 + i) * 2)[0]) for i in range(16)]
bank15 = [rgb555(struct.unpack_from("<H", palb, (15 * 16 + i) * 2)[0]) for i in range(16)]

# 只统计「非空」砖
groups = defaultdict(list)
for t in range(0, 1024):
    b = v[cbase + t * 32: cbase + t * 32 + 32]
    if len(b) < 32:
        break
    if any(b):
        groups[bytes(b)].append(t)

print("== 内容相同的砖分组（仅列 >=2 个成员的组，限 %d..%d）==" % (lo, hi))
for b, ts in sorted(groups.items(), key=lambda kv: kv[1][0]):
    ts = [t for t in ts]
    ins = [t for t in ts if lo <= t <= hi]
    if len(ts) >= 2 and ins:
        print("  成员 %-40s" % ts[:12])
print()

# 渲染 521..hi 的砖图（按 9 号 bank 上色，另附 8、15 号）
n = hi - lo + 1
SC = 4
COLS = 16
rows = (n + COLS - 1) // COLS
im = Image.new("RGB", (COLS * 8 * SC, rows * (8 * SC + 14)), (20, 20, 26))
dr = ImageDraw.Draw(im)
for i, t in enumerate(range(lo, hi + 1)):
    gx, gy = i % COLS, i // COLS
    off = cbase + t * 32
    for y in range(8):
        for x in range(8):
            byte = v[off + y * 4 + x // 2]
            idx = (byte & 0xF) if x % 2 == 0 else (byte >> 4)
            col = bank9[idx]
            if idx == 0:
                col = (0, 0, 0)
            elif idx == 8 and t < 700:
                pass
            for dy in range(SC):
                for dx in range(SC):
                    im.putpixel((gx * 8 * SC + x * SC + dx, gy * (8 * SC + 14) + y * SC + dy), col)
    dr.text((gx * 8 * SC + 2, gy * (8 * SC + 14) + 8 * SC + 1), str(t), fill=(255, 255, 0))
out = os.path.join(T, "thash_%s_%d_%d.png" % (tag, lo, hi))
im.save(out)
print("saved", out, im.size)
