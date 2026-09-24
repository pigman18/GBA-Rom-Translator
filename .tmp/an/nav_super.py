import numpy as np, os
from PIL import Image
FD=r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/graphic/fonts"
g=np.load(r"C:/code/GBA-Rom-Translator/.tmp/an/nav_game_exact.npy")
ink=np.all(g==[33,132,255],axis=2)
raw=open(os.path.join(FD,"PokeRSFontChsMiddle_unshadow(0xE0000).bin"),'rb').read()
def bits(m):
    v=0
    for r in range(16):
        for c in range(8):
            if m[r,c]: v|=1<<(r*8+c)
    return v
L=[]
for i in range(len(raw)//128):
    b=raw[i*128:i*128+64]; m=np.zeros((16,8),bool)
    for k in range(64):
        bb=b[k]; r=k//4; cb=(k%4)*2
        if bb&0x0F: m[r,cb]=True
        if bb&0xF0: m[r,cb+1]=True
    L.append(bits(m))
LS=np.array([bin(v).count('1') for v in L])
print("库字形墨量: min %d max %d mean %.1f"%(LS.min(),LS.max(),LS.mean()))

for (y0,x0,lbl) in ((25,16,"r1c1"),(25,24,"r1c2"),(41,16,"r2c1"),(41,24,"r2c2")):
    S=bits(ink[y0:y0+16, x0:x0+8])
    n=bin(S).count('1')
    viol=np.array([bin(v&~S).count('1') for v in L])
    cov =np.array([bin(v&S ).count('1') for v in L])
    i0=int(viol.argmin())
    print(f"--- {lbl} y{y0} x{x0}: 屏上墨={n}")
    print(f"    最小违规(库有屏无) = {viol[i0]}  @gid {i0}  (库墨 {LS[i0]}, 覆盖 {cov[i0]})  => 屏上墨 - 该字墨 = {n-LS[i0]}")
    idx=np.argsort(viol*1000 - cov)[:5]
    for i in idx:
        print(f"      cand gid={int(i):5d} viol={int(viol[i]):3d} cov={int(cov[i]):3d} libink={int(LS[i]):3d}")
