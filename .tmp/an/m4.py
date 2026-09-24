# -*- coding: utf-8 -*-
"""取墨量最大的格，逐位打印 vs 字库最佳匹配（含 1px 阴影并集候选）。"""
import numpy as np, os
from PIL import Image
ROM = r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba"
D   = r"C:/Users/Administrator/.workbuddy/clipboard-images"
LIBS = {"MIDDLE":0x09400000, "SMALL":0x09100000, "NORMAL":0x09000000}
POP=np.array([bin(i).count("1") for i in range(256)],dtype=np.uint8)

def load_bits(addr,n=7168):
    raw=open(ROM,"rb").read(); off=addr-0x08000000
    a=np.frombuffer(raw[off:off+n*128],dtype=np.uint8).reshape(n,128)
    B=np.zeros((n,16,8),dtype=np.uint8)
    for r in range(16):
        blk = a[:, r*4:r*4+4] if r<8 else a[:, 32+(r-8)*4:32+(r-8)*4+4]
        lo=(blk & 0x0F)>0; hi=(blk >> 4)>0
        for i in range(4):
            B[:,r,i*2]=lo[:,i]; B[:,r,i*2+1]=hi[:,i]
    return B

def ink_mask(png,bgs):
    g=np.array(Image.open(png).convert("RGB").crop((1,47,241,207))).astype(np.int16)
    m=np.ones(g.shape[:2],dtype=bool)
    for b in bgs: m &= (np.abs(g-np.array(b)).sum(2)!=0)
    return m

def show(a,label):
    print(label)
    for r in range(16):
        print("     "+"".join("#" if v else "." for v in a[r]))

def analyze(tag,png,bgs,search):
    m=ink_mask(os.path.join(D,png),bgs)
    H,W=m.shape
    best=None
    for y0 in range(search[1],search[3]):
        for x0 in range(search[0],search[2]):
            if y0+16>H or x0+8>W: continue
            n=int(m[y0:y0+16,x0:x0+8].sum())
            if best is None or n>best[0]: best=(n,x0,y0)
    n,x0,y0=best
    cell=m[y0:y0+16,x0:x0+8]
    print("="*74); print("%s  墨量最大格 (%d,%d) 墨=%d"%(tag,x0,y0,n))
    show(cell,"  [屏幕实际]")
    flat=cell.reshape(16,8).astype(np.uint8)
    # 候选1：原样；候选2：去掉 1px 右下阴影（ink 且 左上也是 ink）
    for name,T in (("原样", flat),):
        for ln,addr in LIBS.items():
            B=load_bits(addr)
            d=np.bitwise_xor(B, T[None,:,:]).sum((1,2))
            i=int(d.argmin())
            print("  [%s · %s] 最佳 gid=%d d=%d/128"%(ln,name,i,int(d[i])))
            show(B[i],"    字库字形：")
            break
        break

analyze("背包列表","clipboard-2026-09-22T05-38-22-116Z-a60c0d90.png",
        [(255,231,173),(255,198,90)],(112,18,152,30))
