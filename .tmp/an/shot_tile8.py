import numpy as np, os
g=np.load(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_native.npy").astype(int)
ink=np.all(g==[33,132,255],axis=2)
FD=r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/graphic/fonts"
def brick(b32):
    m=np.zeros((8,8),bool)
    for i in range(32):
        b=b32[i]; r=i//4; cb=(i%4)*2
        if b&0x0F: m[r,cb]=True
        if b&0xF0: m[r,cb+1]=True
    return m
raw=open(os.path.join(FD,"PokeRSFontChsMiddle_unshadow(0xE0000).bin"),'rb').read()
T=np.array([brick(raw[gid*128 + k*32 : gid*128 + k*32 + 32]) for gid in range(7168) for k in (0,1)])  # (14336,8,8)
meta=[(gid,k) for gid in range(7168) for k in (0,1)]
TI=T.sum(axis=(1,2))
print("库 8x8 砖共", len(T), " 有墨砖:", int((TI>0).sum()))

def show8(m):
    return "".join('#' if m[r,c] else '.' for r in range(8) for c in range(8))

print("\n=== 屏幕 8x8 砖（按 y0 行、x0 列）与库逐砖匹配 ===")
for (y0,lab) in ((24,"row1"),(40,"row2")):
    for x0 in range(16,232,8):
        m=ink[y0:y0+16, x0:x0+8]
        n=int(m.sum())
        if n<4: continue
        top=m[0:8,:]; bot=m[8:16,:]
        out=[]
        for tag,t in (("上",top),("下",bot)):
            if t.sum()<2: out.append(f"{tag}:空"); continue
            d=(T!=t[None,:,:]).sum(axis=(1,2))
            i=int(d.argmin())
            out.append(f"{tag}:d={int(d[i]):2d} gid={meta[i][0]:5d}块{meta[i][1]} 库墨={int(TI[i]):2d} 屏墨={int(t.sum()):2d}")
        print(f"  {lab} x={x0:3d} " + "   ".join(out))
