# -*- coding: utf-8 -*-
"""binrnd.py <tag> <r0> <r1> <c0> <c1> -- 把 map 区域按 tile 值二值渲染（值1=黑 值8=蓝 值15=白）。"""
import struct, sys
from pathlib import Path
from PIL import Image, ImageDraw
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag = sys.argv[1]; r0,r1,c0,c1 = (int(x) for x in sys.argv[2:6])
v = (T/f"drive_{tag}_vram.bin").read_bytes()
CB = 2*0x4000
def nib(t,y,x):
    a = CB+t*32+y*4+(x>>1); b = v[a] if a<len(v) else 0
    return (b>>4) if (x&1)==0 else (b&0xF)
S = 10
W = (c1-c0)*8; H = (r1-r0)*8
im = Image.new("RGB", (W*S+S, H*S+S*3), (255,255,255)); d = ImageDraw.Draw(im)
COL = {1:(220,0,0), 8:(0,0,0), 15:(255,255,255)}
for ri in range(r0, r1):
    for ci in range(c0, c1):
        e = struct.unpack_from("<H", v, 15*0x800 + (ri*32+ci)*2)[0]
        t = e & 0x3FF
        ox, oy = (ci-c0)*8*S, (ri-r0)*8*S
        d.rectangle([ox, oy, ox+8*S-1, oy+8*S-1], outline=(200,200,200))
        if t:
            for y in range(8):
                for x in range(8):
                    nv = nib(t,y,x)
                    d.rectangle([ox+x*S, oy+y*S, ox+x*S+S-1, oy+y*S+S-1], fill=COL.get(nv,(0,200,0)))
            d.text((ox+3, oy+3), "%d" % t, fill=(0,120,255))
im.save(T/f"bin_{tag}_{r0}_{r1}_{c0}_{c1}.png"); print("saved", im.size)
