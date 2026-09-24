# -*- coding: utf-8 -*-
"""屏幕 8x16 格 vs 4bpp 字库全搜（POKEMON_RUBY_AXVJ00_translated.gba_TMP-vs-output）。"""
import numpy as np, os
from PIL import Image
ROM = r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba"
D   = r"C:/Users/Administrator/.workbuddy/clipboard-images"
LIBS = {"MIDDLE":0x09400000, "SMALL":0x09100000, "NORMAL":0x09000000}
POP=np.array([bin(i).count("1") for i in range(256)],dtype=np.uint8)

def load_lib(addr,n=7168):
    raw=open(ROM,"rb").read()
    off=addr-0x08000000
    a=np.frombuffer(raw[off:off+n*128],dtype=np.uint8).reshape(n,128)
    out=np.zeros((n,16),dtype=np.uint8)
    for r in range(16):
        blk = a[:, r*4:r*4+4] if r<8 else a[:, 32+(r-8)*4:32+(r-8)*4+4]
        lo=blk & 0x0F; hi=blk >> 4
        v=np.zeros(n,dtype=np.uint16)
        for i in range(4):
            v=(v<<1)|(lo[:,i]>0); v=(v<<1)|(hi[:,i]>0)
        out[:,r]=v.astype(np.uint8)
    return out

def ink_mask(png, bgs):
    im=Image.open(png).convert("RGB").crop((1,47,241,207))
    g=np.array(im).astype(np.int16)
    m=np.ones(g.shape[:2],dtype=bool)
    for b in bgs:
        m &= (np.abs(g-np.array(b)).sum(2)!=0)
    return m

def cell_bits(m,x0,y0):
    v=0
    for r in range(16):
        b=0
        for c in range(8):
            b=(b<<1)|(1 if m[y0+r,x0+c] else 0)
        v=(v<<8)|b
    return v  # 128-bit int

def sweep(m,xs,ys,L,libname,topk=8):
    res=[]
    for y0 in ys:
        for x0 in xs:
            cand=np.frombuffer(cell_bits(m,x0,y0).to_bytes(16,'big'),dtype=np.uint8)
            d=POP[np.bitwise_xor(L,cand[None,:])].sum(1)
            i=int(d.argmin()); res.append((int(d[i]),int(i),x0,y0,int(cand.sum()!=0)))
    res.sort()
    print("  [%s] 最佳 %d："%(libname,topk))
    for dd,gi,x0,y0,nonz in res[:topk]:
        print("     d=%3d gid=%5d 格(%3d,%3d) 有墨=%d"%(dd,gi,x0,y0,nonz))
    return res

jobs=[
 ("背包列表", "clipboard-2026-09-22T05-38-22-116Z-a60c0d90.png", [(255,231,173),(255,198,90)],
  range(112,152), range(19,28)),
 ("队伍对话框", "clipboard-2026-09-22T05-38-22-117Z-5e57f491.png", [(255,255,255),(242,242,242),(214,214,206)],
  range(4,60), range(136,146)),
 ("地图名牌", "clipboard-2026-09-22T05-38-22-114Z-98d12ab8.png", [(255,255,255),(242,242,242)],
  range(186,232), range(8,145)),
]
for tag,f,bgs,xs,ys in jobs:
    m=ink_mask(os.path.join(D,f),bgs)
    print("="*74); print(tag, " 范围 x",xs.start,"-",xs.stop," y",ys.start,"-",ys.stop)
    for ln,addr in LIBS.items():
        sweep(m,xs,ys,load_lib(addr),ln)
