# -*- coding: utf-8 -*-
"""按 12px 相位规则把 tile 流拼成"屏幕上的字"：
字 k 的列 [0,8) 在 tile A_k、列 [8,11) 在 tile B_k（下一格的 tile）。
上半 = A_k / B_k，下半 = A_k+1 / B_k+1。
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag = sys.argv[1]
bi = int(sys.argv[2]) if len(sys.argv) > 2 else 0
v = (T / f"drive_{tag}_vram.bin").read_bytes()
pal = (T / f"drive_{tag}_pal.bin").read_bytes()
def rgb555(w): return ((w&31)*255//31,((w>>5)&31)*255//31,((w>>10)&31)*255//31)
CB = 2*0x4000

def nib(tile, y, x):
    a = CB + tile*32 + y*4 + (x>>1)
    b = v[a] if a < len(v) else 0
    return (b>>4) if (x&1)==0 else (b&0xF)

def render_ink(tile, y, x, ink_lo, ink_hi, bg):
    n = nib(tile, y, x)
    return (0,0,0) if (n != 15 and n != 0) else (255,255,255)

# 一行 4 个字的 tile 起点序列（取自 map：527,529,531,533 表示每字跨 2 格）
starts = [int(s) for s in sys.argv[3].split(",")]
S = 14
im = Image.new("RGB", (len(starts)*12*S, 16*S), (255,255,255))
d = ImageDraw.Draw(im)
for k, t0 in enumerate(starts):
    ox = k*12*S
    # 字的上半：列0-7 来自 t0，列8-11 来自 t0+2
    for y in range(8):
        for x in range(8):
            d.rectangle([ox+x*S, y*S, ox+x*S+S-1, y*S+S-1], fill=render_ink(t0, y, x, 1, 15, 15))
        for x in range(3):
            d.rectangle([ox+(8+x)*S, y*S, ox+(8+x)*S+S-1, y*S+S-1], fill=render_ink(t0+2, y, x, 1, 15, 15))
    for y in range(8):
        for x in range(8):
            d.rectangle([ox+x*S, (8+y)*S, ox+x*S+S-1, (8+y)*S+S-1], fill=render_ink(t0+1, y, x, 1, 15, 15))
        for x in range(3):
            d.rectangle([ox+(8+x)*S, (8+y)*S, ox+(8+x)*S+S-1, (8+y)*S+S-1], fill=render_ink(t0+3, y, x, 1, 15, 15))
    d.text((ox+2, 2), str(t0), fill=(255,0,0))
im.save(T / f"join_{tag}.png"); print("saved", im.size)
