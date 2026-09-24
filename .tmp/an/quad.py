import numpy as np
P=r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/graphic/fonts/PokeRSFontChsMiddle_unshadow(0xE0000).bin"
raw=open(P,'rb').read()
def brick(b32):
    m=np.zeros((8,8),np.uint8)
    for i in range(32):
        b=b32[i]; r=i//4; cb=(i%4)*2
        if b&0x0F: m[r,cb]=1
        if b&0xF0: m[r,cb+1]=1
    return m
def show(m,label):
    print("   "+label)
    for r in range(8):
        print("     "+"".join('#' if m[r,c] else '.' for c in range(8)))

for gid in (0,1,2,100,1000):
    g=raw[gid*128:(gid+1)*128]
    TL,TR,BL,BR = g[0:32],g[32:64],g[64:96],g[96:128]
    print(f"=== gid {gid}  ink per 32B chunk: TL={sum(bin(x).count('1') for x in TL)} TR={sum(bin(x).count('1') for x in TR)} BL={sum(bin(x).count('1') for x in BL)} BR={sum(bin(x).count('1') for x in BR)}")
    show(brick(TL),"TL bytes0..31"); show(brick(TR),"TR bytes32..63")
    show(brick(BL),"BL bytes64..95"); show(brick(BR),"BR bytes96..127")
