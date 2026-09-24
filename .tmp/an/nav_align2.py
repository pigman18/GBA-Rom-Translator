import numpy as np, os
FD=r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/graphic/fonts"
g=np.load(r"C:/code/GBA-Rom-Translator/.tmp/an/nav_game_exact.npy")
ink=np.all(g==[33,132,255],axis=2)
raw=open(os.path.join(FD,"PokeRSFontChsMiddle_unshadow(0xE0000).bin"),'rb').read()
L=[]
for i in range(len(raw)//128):
    b=raw[i*128:i*128+64]; v=0
    for k in range(64):
        bb=b[k]; r=k//4; cb=(k%4)*2
        if bb&0x0F: v|=1<<(r*8+cb)
        if bb&0xF0: v|=1<<(r*8+cb+1)
    L.append(v)
LS=np.array([bin(v).count('1') for v in L])
sel=[i for i in range(len(L)) if LS[i]>=25]
print("候选字库字形(viol 优先, 取覆盖最大)")
best=[]
for dy in range(20,46):
 for dx in range(12,52):
    if dx+8>240 or dy+16>160: continue
    S=0
    for r in range(16):
        for c in range(8):
            if ink[dy+r,dx+c]: S|=1<<(r*8+c)
    n=bin(S).count('1')
    if n<20: continue
    bv=999; bi=-1; bc=0
    for i in sel:
        vi=bin(L[i]&~S).count('1')
        if vi<bv:
            bv=vi; bi=i; bc=bin(L[i]&S).count('1')
        elif vi==bv:
            c2=bin(L[i]&S).count('1')
            if c2>bc: bi=i; bc=c2
    best.append((bv,-bc,dy,dx,bi,n,bc))
best.sort()
print("TOP 12  (违规, -覆盖, dy, dx, gid, 屏墨, 覆盖)")
for b in best[:12]:
    print("   viol=%d cov=%d dy=%d dx=%d gid=%d 屏墨=%d"%(b[0],b[6],b[2],b[3],b[4],b[5]))
