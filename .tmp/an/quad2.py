import numpy as np
P=r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/graphic/fonts/PokeRSFontChsMiddle_unshadow(0xE0000).bin"
raw=open(P,'rb').read()
def brick(b32):
    m=np.zeros((8,8),int)
    for i in range(32):
        b=b32[i]; r=i//4; cb=(i%4)*2
        if b&0x0F: m[r,cb]=1
        if b&0xF0: m[r,cb+1]=1
    return m
def ink(b32): return int(brick(b32).sum())
def show(m,lbl):
    print("      "+lbl)
    for r in range(8): print("        "+"".join('#' if m[r,c] else '.' for c in range(8)))

print("### 每个 32B 块的墨量统计（全库 7168 字） ###")
tot=[0,0,0,0]; nz=[0,0,0,0]
for gid in range(7168):
    g=raw[gid*128:(gid+1)*128]
    for k in range(4):
        v=ink(g[k*32:(k+1)*32]); tot[k]+=v
        if v: nz[k]+=1
for k in range(4):
    print(f"  块{k} (bytes {k*32}..{k*32+31}): 总墨 {tot[k]:8d}  有墨字数 {nz[k]:5d}/7168")

print()
for gid in (0,1,2,3):
    g=raw[gid*128:(gid+1)*128]
    print(f"=== gid {gid}: 块墨量 {[ink(g[k*32:(k+1)*32]) for k in range(4)]}")
    for k in range(4):
        show(brick(g[k*32:(k+1)*32]), f"块{k} bytes {k*32}..{k*32+31}")
