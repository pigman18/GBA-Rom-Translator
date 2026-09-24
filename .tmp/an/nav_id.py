import numpy as np, itertools
from PIL import Image

LIB = r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/graphic/fonts/PokeRSFontChsMiddle_unshadow(0xE0000).bin"
raw = open(LIB,'rb').read()
NG = len(raw)//128
assert NG==7168, NG

def glyph_int(b64):
    v=0
    for i in range(64):
        b=b64[i]; row=i//4; cb=(i%4)*2
        if b & 0x0F: v |= 1 << (row*8+cb)
        if b & 0xF0: v |= 1 << (row*8+cb+1)
    return v

GI = [glyph_int(raw[g*128:g*128+64]) for g in range(NG)]
print("lib glyphs", NG, "sample ink counts:", [bin(GI[i]).count('1') for i in (0,1,2)])

im = Image.open(r"C:/Users/Administrator/.workbuddy/clipboard-images/clipboard-2026-09-22T08-09-07-691Z-95ff2422.png").convert("RGB")
a = np.array(im)

def build(ox,oy,sc):
    g = a[oy:oy+160*sc, ox:ox+240*sc]
    if g.shape[0]!=160*sc or g.shape[1]!=240*sc: return None
    return g.reshape(160, sc, 240, sc, 3).mean(axis=(1,3))

def inkmask(game):
    r,g,b = game[:,:,0],game[:,:,1],game[:,:,2]
    return ((b>150)&(r<120)).astype(np.uint8)

best_global=None
for oy in (54,55):
    game=build(1,oy,3)
    if game is None: print("bad geom oy",oy); continue
    S=inkmask(game)
    tot=int(S.sum())
    print(f"--- oy={oy} total blue px={tot}")
    hits=[]
    for wy in range(20,132):
        for wx in range(6,236):
            cell=S[wy:wy+16, wx:wx+8]
            n=int(cell.sum())
            if n<4: continue
            v=glyph_int(np.array([ (cell[i//4*4:(i//4*4)+4] if False else 0) for i in range(64)])) # placeholder
            # 正确打包
            v=0
            for row in range(16):
                for col in range(8):
                    if cell[row,col]: v |= 1 << (row*8+col)
            bp=v.bit_count()
            bd=999; bg=-1
            for gi,gi_int in enumerate(GI):
                if gi_int.bit_count()!=0 and abs(gi_int.bit_count()-bp)>6: continue
                d=(v^gi_int).bit_count()
                if d<bd: bd=d; bg=gi
            hits.append((bd,wy,wx,bg))
    hits.sort()
    print("TOP 30 matches (d, y, x, gid):")
    for h in hits[:30]:
        print("   ",h)
