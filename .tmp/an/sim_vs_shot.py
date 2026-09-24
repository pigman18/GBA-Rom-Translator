# -*- coding: utf-8 -*-
"""并排对比：模拟渲染的汉字（大图） vs 截图实际的中文块（大图）。"""
import numpy as np
from PIL import Image, ImageDraw
import sys
sys.path.insert(0, r"C:\code\GBA-Rom-Translator\.tmp\an")
from sim_engine import Engine, gid_of, render   # 复用模拟器

a = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\shot_native.npy").astype(int)
blue = (np.abs(a - np.array([33, 132, 255])).sum(axis=2) < 60)

Z = 12
def tiles_from_screen(x0, y0, ntile):
    return blue[y0:y0 + 16, x0:x0 + 8 * ntile]

def paint(mat, Z=Z, title=""):
    h, w = mat.shape
    im = Image.new("RGB", (w * Z + 8, h * Z + 26), (24, 24, 28))
    d = ImageDraw.Draw(im)
    for y in range(h):
        for x in range(w):
            d.rectangle([4 + x * Z, 22 + y * Z, 4 + (x + 1) * Z - 1, 22 + (y + 1) * Z - 1],
                        fill=(40, 140, 255) if mat[y, x] else (245, 245, 250))
    d.text((4, 6), title, fill=(255, 220, 120))
    return im

def sim_tiles(text, tile_base, fg, bg):
    e = Engine(tile_base=tile_base, fg=fg, bg=bg)
    for ch in text:
        g = gid_of(ch)
        if g is not None:
            e.emit(g, ch)
    W = len(text) * 8
    img = np.zeros((16, W), bool)
    m = {}
    for row, col, tile, pal in e.tilemap:
        m[(row, col)] = tile
    for (row, col), tile in m.items():
        for ty in range(8):
            for tx in range(8):
                byte = e.vram[tile * 32 + ty * 4 + tx // 2]
                v = (byte >> 4) if (tx % 2) else (byte & 0x0F)
                x, y = col * 8 + tx, row * 8 + ty
                if 0 <= x < W and 0 <= y < 16:
                    img[y, x] = (v == 15)
    return img

sim = sim_tiles("领航员时间返回继续", 1, 15, 0)
scr = tiles_from_screen(16, 24, 16)     # x16..143, y24..39

A = paint(sim, title="SIMULATED (engine.c math, 9 chars x 8px)")
B = paint(scr, title="SCREENSHOT actual (x16..143, y24..39)")
C = paint(blue[26:37, 16:144], title="SCREENSHOT ink-only y26..36")

W = max(A.width, B.width, C.width)
H = A.height + B.height + C.height + 20
out = Image.new("RGB", (W, H), (16, 16, 20))
y = 0
for i in (A, B, C):
    out.paste(i, (0, y)); y += i.height + 10
p = r"C:\code\GBA-Rom-Translator\.tmp\an\sim_vs_shot.png"
out.save(p)
print("saved", p, out.size)
print("模拟：9 字 72px 宽；截图块：128px 宽")
