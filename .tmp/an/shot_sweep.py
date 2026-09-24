import numpy as np, os
g=np.load(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_native.npy").astype(int)
FD=r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/graphic/fonts"
def l4(b64):
    out=np.zeros((16,8),bool)
    for i in range(64):
        b=b64[i]; r=i//4; cb=(i%4)*2
        if b&0x0F: out[r,cb]=True
        if b&0xF0: out[r,cb+1]=True
    return out
raw=open(os.path.join(FD,"PokeRSFontChsMiddle_unshadow(0xE0000).bin"),'rb').read()
L=np.array([l4(raw[i*128:i*128+64]) for i in range(7168)])
LI=L.sum(axis=(1,2))
ink=np.all(g==[33,132,255],axis=2)   # 精确墨水色

print("精确墨水色 px:", int(ink.sum()))
print()
print("=== 全对齐扫描：屏幕 16x8 窗口 vs 全库，逐 (dy,dx) 取最优 ===")
res=[]
for dy in range(20,46):
  for dx in range(12,60):
    if dy+16>160 or dx+8>240: continue
    m=ink[dy:dy+16, dx:dx+8]
    n=int(m.sum())
    if n<10: continue
    d=(L!=m[None,:,:]).sum(axis=(1,2))
    i=int(d.argmin())
    res.append((int(d[i]),dy,dx,i,n,int(LI[i])))
res.sort()
for r in res[:20]:
    print(f"   d={r[0]:3d} dy={r[1]:3d} dx={r[2]:3d} gid={r[3]:5d} 屏墨={r[4]:3d} 库墨={r[5]:3d}")
