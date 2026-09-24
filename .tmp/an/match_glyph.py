# -*- coding: utf-8 -*-
"""把屏幕上的 8x16 格拿去 4bpp 字库全搜（origin-vs-output 逐位比对）。
字库 128B/字 = [0:32)TL [32:64)BL [64:96)TR [96:128)BR，低 nibble 在左。
屏幕格高 16 行 = TL(行0..7) + BL(行8..15)。"""
import numpy as np, os, sys, struct
from PIL import Image

ROM = r"C:/code/GBA-Rom-Translator/roms/origin/POKEMON_RUBY_AXVJ00.gba"
D   = r"C:/Users/Administrator/.workbuddy/clipboard-images"
LIBS = {"MIDDLE": 0x09400000, "SMALL": 0x09100000, "NORMAL": 0x09000000}

def load_lib(addr, n=7168):
    with open(ROM,"rb") as f:
        f.seek(addr-0x08000000); raw=f.read(n*128)
    out=[]
    for g in range(n):
        cell=raw[g*128:(g+1)*128]
        rows=[]
        for r in range(16):
            b = cell[(r*4):(r*4)+4] if r<8 else cell[32+(r-8)*4:32+(r-8)*4+4]
            v=0
            for i,byte in enumerate(b):
                lo=byte&0x0F; hi=byte>>4
                v = (v<<1)|(1 if lo else 0)
                v = (v<<1)|(1 if hi else 0)
            rows.append(v)
        out.append(rows)
    return np.array(out, dtype=np.uint8)   # (n,16)

def screen_mask(path, box):
    im=Image.open(path).convert("RGB")
    g=np.array(im.crop(box)).astype(int)
    return g

def cell_bits(mask, x0, y0):
    """mask: HxWx3 -> 16 bytes，每字节 8 位（bit7=最左像素）"""
    rows=[]
    for r in range(16):
        v=0
        for c in range(8):
            v=(v<<1) | (1 if mask[y0+r, x0+c].any() else 0)
        rows.append(v)
    return np.array(rows, dtype=np.uint8)

POP=np.array([bin(i).count("1") for i in range(256)],dtype=np.uint8)

def sweep(mask, xs, ys, lib, name, topk=6):
    res=[]
    for y0 in ys:
        for x0 in xs:
            cand=cell_bits(mask,x0,y0)
            d=POP[np.bitwise_xor(lib, cand[None,:])].sum(1)
            i=int(d.argmin())
            res.append((int(d[i]), int(i), x0, y0))
    res.sort()
    print("  --%s-- 最佳 %d 个：" % (name, topk))
    for dd,gi,x0,y0 in res[:topk]:
        print("     d=%3d gid=%5d (0x%04X)  格(%3d,%3d)" % (dd,gi,gi,x0,y0))
    return res

def run(png, box, xs, ys, tag):
    im=Image.open(png).convert("RGB")
    g=np.array(im.crop((1,47,241,207))).astype(int)   # 游戏视口
    # 只保留 box 内的像素，其它置 0，避免越界
    x0b,y0b,x1b,y1b=box
    m=np.zeros(g.shape[:2],dtype=bool)
    m[y0b:y1b, x0b:x1b]=True
    print("="*70); print(tag, "box=",box)
    for ln,lib in LIBS.items():
        L=load_lib(lib)
        sweep(g, xs, ys, L, ln)

if __name__=="__main__":
    bag=os.path.join(D,"clipboard-2026-09-22T05-38-22-116Z-a60c0d90.png")
    run(bag,(112,18,160,40), range(112,150), range(19,27), "背包 y18-40")
