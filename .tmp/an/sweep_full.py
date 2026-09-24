import numpy as np, os
g=np.load(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_native.npy").astype(int)
ink=np.all(g==[33,132,255],axis=2)
FD=r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/graphic/fonts"
def l4(b64):
    out=np.zeros((16,8),bool)
    for i in range(64):
        b=b64[i]; r=i//4; cb=(i%4)*2
        if b&0x0F: out[r,cb]=True
        if b&0xF0: out[r,cb+1]=True
    return out
raw=open(os.path.join(FD,"PokeRSFontChsMiddle(0xE0000).bin"),'rb').read()
L=np.array([l4(raw[i*128:i*128+64]) for i in range(7168)])
LI=L.sum(axis=(2,1))
# 归一化距离：d / max(屏墨,库墨)
res=[]
for dy in range(18,46):
  for dx in range(12,233):
    if dy+16>160 or dx+8>240: continue
    m=ink[dy:dy+16,dx:dx+8]; n=int(m.sum())
    if n<20: continue
    d=(L!=m[None,:,:]).sum(axis=(2,1))
    i=int(d.argmin())
    score=d[i]/max(n,int(LI[i]),1)
    res.append((float(score),int(d[i]),dy,dx,i,n,int(LI[i])))
res.sort()
print("TOP 25  (归一化距离, d, dy, dx, gid, 屏墨, 库墨)")
for r in res[:25]:
    print(f"   {r[0]:.3f}  d={r[1]:3d} dy={r[2]:3d} dx={r[3]:3d} gid={r[4]:5d} 屏墨={r[5]:3d} 库墨={r[6]:3d}")
