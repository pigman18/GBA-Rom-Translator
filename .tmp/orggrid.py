# -*- coding: utf-8 -*-
"""orggrid.py — 原版设置页(org2) BG0 的「砖号网格 + 像素图」一次出全。
目的：看原版到底怎么给「同一行里多个字」发号（号 = 位置？号 = 字形？）。
用法: python orggrid.py [tag] [bg] [scale]
"""
import os, re, struct, sys
from PIL import Image

T = r"C:\code\GBA-Rom-Translator\.tmp"
TAG = sys.argv[1] if len(sys.argv) > 1 else "org2"
BG  = int(sys.argv[2]) if len(sys.argv) > 2 else 0
SC  = int(sys.argv[3]) if len(sys.argv) > 3 else 3

v = open(os.path.join(T, "drive_%s_vram.bin" % TAG), "rb").read()
txt = open(os.path.join(T, "drive_%s.log" % TAG), encoding="utf-8", errors="replace").read()
io = {}
for m in re.finditer(r"\[io\] IO (\w+) 0x[0-9a-fA-F]+:\s*(0x[0-9a-fA-F]+)", txt):
    io[m.group(1)] = int(m.group(2), 16)

DISPCNT = io["DISPCNT"]
CNT = io["BG%dCNT" % BG]
cb = (CNT >> 2) & 3
sb = (CNT >> 8) & 0x1F
cbase = cb * 0x4000
mbase = sb * 0x800
print("tag=%s BG%d CNT=%04X cb=%d sb=%d charbase=%05X map=%05X" % (TAG, BG, CNT, cb, sb, cbase, mbase))
print("DISPCNT=%04X  on=%d" % (DISPCNT, (DISPCNT >> (8 + BG)) & 1))

# --- 像素图（按调色板索引 0..15 映射灰度：0=白 15=黑，其余线性）---
pal = {}
for i in range(16):
    g = 255 - int(i * 255 / 15)
    pal[i] = (g, g, g)
im = Image.new("RGB", (256, 256), (60, 60, 60))
for r in range(32):
    for c in range(32):
        t = struct.unpack_from("<H", v, mbase + (r * 32 + c) * 2)[0] & 0x3FF
        off = cbase + t * 32
        for y in range(8):
            for x in range(8):
                b = v[off + y * 4 + x // 2]
                idx = (b & 0xF) if x % 2 == 0 else (b >> 4)
                im.putpixel((c * 8 + x, r * 8 + y), pal[idx])
im.resize((256 * SC, 256 * SC), Image.NEAREST).save(os.path.join(T, "orggrid_%s_bg%d.png" % (TAG, BG)))
print("-> .tmp/orggrid_%s_bg%d.png" % (TAG, BG))

# --- 砖号网格 ---
print("      " + "".join("%5d" % c for c in range(30)))
for r in range(20):
    row = [struct.unpack_from("<H", v, mbase + (r * 32 + c) * 2)[0] & 0x3FF for c in range(30)]
    print("r%02d  " % r + "".join("%5d" % t for t in row))
