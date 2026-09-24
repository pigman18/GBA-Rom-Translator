# -*- coding: utf-8 -*-
"""tilesheet.py — 把原版设置页每个「文字格位」的字形(t,t+1 竖直对)渲染成带号贴图。
判定：同一字形是否复用同一对砖号（= 号是字形的函数），还是每处一份（= 号是位置的函数）。
用法: python tilesheet.py [tag] [bg]
"""
import os, re, struct, sys
from PIL import Image, ImageDraw

T = r"C:\code\GBA-Rom-Translator\.tmp"
TAG = sys.argv[1] if len(sys.argv) > 1 else "org2"
BG = int(sys.argv[2]) if len(sys.argv) > 2 else 0
CELL = 6           # 每像素放大
GAP = 4
LAB = 14

v = open(os.path.join(T, "drive_%s_vram.bin" % TAG), "rb").read()
txt = open(os.path.join(T, "drive_%s.log" % TAG), encoding="utf-8", errors="replace").read()
io = {}
for m in re.finditer(r"\[io\] IO (\w+) 0x[0-9a-fA-F]+:\s*(0x[0-9a-fA-F]+)", txt):
    io[m.group(1)] = int(m.group(2), 16)
CNT = io["BG%dCNT" % BG]
cbase = ((CNT >> 2) & 3) * 0x4000
mbase = ((CNT >> 8) & 0x1F) * 0x800


def pix(t, x, y):
    b = v[cbase + t * 32 + y * 4 + x // 2]
    return (b & 0xF) if x % 2 == 0 else (b >> 4)


def gray(i):
    g = 255 - int(i * 255 / 15)
    return (g, g, g)


def tile_img(t):
    im = Image.new("RGB", (8 * CELL, 8 * CELL))
    for y in range(8):
        for x in range(8):
            for dy in range(CELL):
                for dx in range(CELL):
                    im.putpixel((x * CELL + dx, y * CELL + dy), gray(pix(t, x, y)))
    return im


FRAME = set(range(512, 521))
rows = []
for r in range(0, 19):
    u, l = r, r + 1
    cells = []
    for c in range(30):
        tu = struct.unpack_from("<H", v, mbase + (u * 32 + c) * 2)[0] & 0x3FF
        tl = struct.unpack_from("<H", v, mbase + (l * 32 + c) * 2)[0] & 0x3FF
        if tu in FRAME or tu == 0:
            continue
        if tl != tu + 1:
            continue
        cells.append((c, tu))
    if len(cells) >= 2:
        rows.append((r, cells))

W = max(len(c) for _, c in rows) * (8 * CELL + GAP)
H = len(rows) * (16 * CELL + LAB + GAP)
im = Image.new("RGB", (W, H), (30, 30, 40))
dr = ImageDraw.Draw(im)
seen = {}
y = 0
for r, cells in rows:
    x = 0
    for c, t in cells:
        im.paste(tile_img(t), (x, y))
        im.paste(tile_img(t + 1), (x, y + 8 * CELL))
        dr.text((x + 1, y + 16 * CELL), "%d@%d" % (t, c), fill=(255, 220, 120))
        seen.setdefault(t, []).append((r, c))
        x += 8 * CELL + GAP
    y += 16 * CELL + LAB + GAP
im.save(os.path.join(T, "tilesheet_%s_bg%d.png" % (TAG, BG)))
print("-> .tmp/tilesheet_%s_bg%d.png   (%d 行文字)" % (TAG, BG, len(rows)))

print("\n== 每个字形(t,t+1) 被几个格位引用 ==")
multi = {k: s for k, s in seen.items() if len(s) > 1}
print("文字格位总数 %d   不同字形 %d   其中被复用 %d 种"
      % (sum(len(s) for s in seen.values()), len(seen), len(multi)))
for k, s in sorted(multi.items(), key=lambda kv: -len(kv[1]))[:12]:
    print("   t=%d  引用 %d 处: %s" % (k, len(s), s))
