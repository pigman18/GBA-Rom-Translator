import numpy as np, os
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
for (y0,x0,lbl) in ((25,16,"r1c1"),(25,24,"r1c2"),(41,16,"r2c1"),(41,24,"r2c2")):
    S=bits(ink[y0:y0+16, x0:x0+8]); n=bin(S).count('1')
    viol=np.array([bin(v&~S).count('1') for v in L])
    cov =np.array([bin(v&S ).count('1') for v in L])
    print("--- %s 屏上墨=%d"%(lbl,n))
    for vt in (0,1,2,3):
        m=(viol<=vt)&(LS>=15)
        if not m.any(): print("    viol<=%d : 无候选"%vt); continue
        c=cov.copy(); c[~m]=-1
        i=int(c.argmax())
        print("    viol<=%d 最佳: gid=%d 库墨=%d 覆盖=%d 违规=%d  => 屏上未解释墨=%d"%(vt,i,LS[i],cov[i],viol[i],n-LS[i]))
