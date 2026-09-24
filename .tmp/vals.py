# -*- coding: utf-8 -*-
"""vals.py <tag> <t0> <t1> — 按 nibble 值着色画砖：1(墨)=黑 8(阴影)=灰 14=紫 15(底)=白 0=浅蓝"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
v = (T / f"drive_{sys.argv[1]}_vram.bin").read_bytes()
lo, hi = int(sys.argv[2]), int(sys.argv[3])
CB = 2*0x4000
COL = {0:(200,220,255), 1:(0,0,0), 8:(170,170,170), 14:(180,0,200), 15:(255,255,255)}
COLS = 16
n = hi - lo
rows = (n + COLS - 1)//COLS
S = 7
im = Image.new("RGB", (COLS*8*S, rows*8*S), (255,255,255))
d = ImageDraw.Draw(im)
for k in range(n):
    t = lo + k
    ox, oy = (k % COLS)*8*S, (k//COLS)*8*S
    for y in range(8):
        for x in range(8):
            a = CB + t*32 + y*4 + (x>>1)
            b = v[a] if a < len(v) else 0
            nv = (b>>4) if (x&1)==0 else (b&0xF)
            d.rectangle([ox+x*S, oy+y*S, ox+x*S+S-1, oy+y*S+S-1], fill=COL.get(nv,(0,255,0)))
    d.rectangle([ox, oy, ox+8*S-1, oy+8*S-1], outline=(255,0,0))
    d.text((ox+2, oy+2), str(t), fill=(0,128,255))
im.save(T / f"vals_{sys.argv[1]}_{lo}_{hi}.png"); print("saved", im.size)
