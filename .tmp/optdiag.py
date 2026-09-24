# -*- coding: utf-8 -*-
"""optdiag.py — 设置页 BG0 逐格诊断：谁引用了 >=512 的号？那些砖长什么样？

判据级问题：optIO dump 里 BG0(cb2) 的 map 引用了 512..520。
这 9 个号物理落在 0x0600C000（cb3 块首）。
它们到底是 (a) 设置页自己的静态美术，还是 (b) 我们钩子写的中文字模？
-> 直接把像素画出来看。
"""
import os
import re
import struct
from PIL import Image

T = r"C:\code\GBA-Rom-Translator\.tmp"
VRAM = 0x06000000
TAG = "optIO"


def load(tag):
    v = open(os.path.join(T, "drive_%s_vram.bin" % tag), "rb").read()
    txt = open(os.path.join(T, "drive_%s.log" % tag), encoding="utf-8", errors="replace").read()
    io = {}
    for m in re.finditer(r"\[io\] IO (\w+) 0x[0-9a-fA-F]+:\s*(0x[0-9a-fA-F]+)", txt):
        io[m.group(1)] = int(m.group(2), 16)
    return v, io


def tile_px(v, off):
    """4bpp 8x8 -> 8x8 灰度列表"""
    out = []
    for y in range(8):
        row = []
        for x in range(8):
            b = v[off + y * 4 + x // 2]
            row.append((b & 0xF) if x % 2 == 0 else (b >> 4))
        out.append(row)
    return out


def strip(v, tiles, aoff, cols=16, scale=6):
    rows = (len(tiles) + cols - 1) // cols
    im = Image.new("RGB", (cols * 8 * scale + (cols + 1) * 2,
                           rows * 8 * scale + (rows + 1) * 2), (40, 40, 48))
    px = im.load()
    for i, t in enumerate(tiles):
        gx, gy = i % cols, i // cols
        ox = 2 + gx * (8 * scale + 2)
        oy = 2 + gy * (8 * scale + 2)
        tp = tile_px(v, aoff + t * 32)
        for y in range(8):
            for x in range(8):
                c = tp[y][x]
                col = (0, 0, 0) if c == 0 else (255, 255, 255)
                for dy in range(scale):
                    for dx in range(scale):
                        px[ox + x * scale + dx, oy + y * scale + dy] = col
    return im


v, io = load(TAG)
dis = io["DISPCNT"]
print("DISPCNT=%04X  BG0CNT=%04X BG1CNT=%04X BG2CNT=%04X BG3CNT=%04X" %
      (dis, io.get("BG0CNT", 0), io.get("BG1CNT", 0), io.get("BG2CNT", 0), io.get("BG3CNT", 0)))
cnt = io["BG0CNT"]
cb = (cnt >> 2) & 3
sb = (cnt >> 8) & 0x1F
size = (cnt >> 14) & 3
cbase = cb * 0x4000
mbase = sb * 0x800
print("BG0 cb=%d cbase=%05X sb=%d mbase=%05X size=%d" % (cb, VRAM + cbase, sb, VRAM + mbase, size))

cells = {}
for ty in range(32 << size):
    for tx in range(32):
        o = mbase + (ty * 32 + tx) * 2
        t = struct.unpack_from("<H", v, o)[0] & 0x3FF
        cells[(tx, ty)] = t

hi = sorted([c for c, t in cells.items() if t >= 512])
print("引用 >=512 的格子数 =", len(hi))
print("  坐标(x,y tile) + 号:")
for c in hi:
    print("    x=%2d y=%2d -> %d" % (c[0], c[1], cells[c]))

# 渲染三张：整层 / 只画<512 / 高号砖条
W = 240
H = 160
allim = Image.new("RGB", (W, H), (0, 0, 0))
loim = Image.new("RGB", (W, H), (0, 0, 0))
pal = [(0, 0, 0), (60, 60, 60), (120, 120, 120), (180, 180, 180),
       (255, 255, 255), (255, 0, 0), (0, 255, 0), (0, 128, 255)]
for ty in range(32 << size):
    for tx in range(32):
        t = cells[(tx, ty)]
        px0 = tx * 8
        py0 = ty * 8
        if px0 >= W or py0 >= H:
            continue
        tp = tile_px(v, cbase + t * 32)
        for y in range(8):
            for x in range(8):
                if px0 + x >= W or py0 + y >= H:
                    continue
                c = tp[y][x]
                a = pal[c & 7]
                allim.putpixel((px0 + x, py0 + y), a)
                if t < 512:
                    loim.putpixel((px0 + x, py0 + y), a)
                else:
                    loim.putpixel((px0 + x, py0 + y), (255, 0, 255))

allim.resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(T, "diag_opt_all.png"))
loim.resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(T, "diag_opt_lo.png"))

# 高号砖的像素条：物理 offset = cbase + t*32
hit = sorted(set(t for t in cells.values() if t >= 512))
strip(v, hit, cbase).save(os.path.join(T, "diag_opt_hitiles.png"))
print("高号砖清单:", hit)

# 另存 cb3 块首 32 砖（物理 0x0600C000 = cb3 的 tile 0..31）
strip(v, list(range(32)), 3 * 0x4000).save(os.path.join(T, "diag_opt_cb3head.png"))
print("saved: diag_opt_all.png diag_opt_lo.png diag_opt_hitiles.png diag_opt_cb3head.png")
