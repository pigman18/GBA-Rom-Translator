# -*- coding: utf-8 -*-
"""atlas2.py <tag> <lo> <hi> — 把 charBase 层内的 [lo,hi) 号砖拼成图集（真调色板，bank0）。"""
import struct, sys
from pathlib import Path
from PIL import Image, ImageDraw
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
def rgb555(w): return ((w&31)*255//31, ((w>>5)&31)*255//31, ((w>>10)&31)*255//31)
tag = sys.argv[1]; lo = int(sys.argv[2]); hi = int(sys.argv[3])
v = (T / f"drive_{tag}_vram.bin").read_bytes()
pal = (T / f"drive_{tag}_pal.bin").read_bytes()
cbase = 2 * 0x4000          # 设置页 tm1 层 charBase=2
COLS = 16
n = hi - lo
rows = (n + COLS - 1) // COLS
S = 3
im = Image.new("RGB", (COLS*8*S, rows*8*S), (30, 30, 30))
d = ImageDraw.Draw(im)
for k in range(n):
    t = lo + k
    cx, cy = (k % COLS)*8*S, (k // COLS)*8*S
    for y in range(8):
        for x in range(8):
            a = cbase + t*32 + y*4 + (x>>1)
            byte = v[a] if a < len(v) else 0
            idx = (byte>>4) if (x & 1) == 0 else (byte & 0xF)
            col = rgb555(struct.unpack_from("<H", pal, idx*2)[0])
            d.rectangle([cx+x*S, cy+y*S, cx+x*S+S-1, cy+y*S+S-1], fill=col)
    d.text((cx+2, cy+1), str(t), fill=(0,255,0))
out = T / f"atlas_{tag}_{lo}_{hi}.png"
im.save(out); print("saved", out, im.size)
