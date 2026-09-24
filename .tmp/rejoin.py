# -*- coding: utf-8 -*-
"""rejoin.py <tag> <bg> <baseTile> <nChars>  -- 按 12px 相位把 map 砖重组为字并放大。"""
import struct, sys
from pathlib import Path
from PIL import Image, ImageDraw
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag, bi = sys.argv[1], int(sys.argv[2])
baset, nch = int(sys.argv[3]), int(sys.argv[4])
v = (T / f"drive_{tag}_vram.bin").read_bytes()
pal = (T / f"drive_{tag}_pal.bin").read_bytes()
CB = 2*0x4000
def rgb(w): return ((w&31)*255//31, ((w>>5)&31)*255//31, ((w>>10)&31)*255//31)
def nib(t, y, x):
    a = CB + t*32 + y*4 + (x>>1)
    b = v[a] if a < len(v) else 0
    return (b>>4) if (x&1)==0 else (b&0xF)

# 屏幕像素列 -> 取哪对格。 相位规则：字 k 起点像素 = 12k(相对槽起点)
# 我方实现：tile 序列 base, base+2, base+4...; 字 k 上半覆盖 tile[?]..
# 直接按“字内列 c (0..11) -> 全局列 12k+c -> tile 索引 (12k+c)//8, 内偏移 (12k+c)%8”
S = 12
im = Image.new("RGB", (nch*14*S, 18*S), (255,255,255))
d = ImageDraw.Draw(im)
for k in range(nch):
    ox = k*14*S + S
    for r in range(11):
        for c in range(11):
            g = 12*k + c
            ti, off = g // 8, g % 8
            t = baset + 2*ti
            yy = 2 + r          # row_off=2
            # 上半/下半：yy<8 -> 上半 tile；否则下半 tile (t+1)
            tile = t if yy < 8 else t + 1
            val = nib(tile, yy & 7, off)
            col = (0,0,0) if val in (1,8) else None
            if col:
                d.rectangle([ox+c*S, r*S, ox+c*S+S-1, r*S+S-1], fill=col)
    d.rectangle([ox-S//2, 0, ox+11*S+S//2-1, 11*S-1], outline=(255,0,0))
    d.text((ox+2, 11*S+4), "char%d" % k, fill=(0,0,255))
im.save(T / f"rj_{tag}_{baset}.png"); print("saved", im.size)
