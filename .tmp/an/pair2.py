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
L=np.array([l4(raw[i*128:i*128+64]).reshape(-1) for i in range(7168)],dtype=np.float32)  # (7168,128)
LS=L.sum(axis=1)

for (y0,lab) in ((24,"row1"),(40,"row2")):
    for x0 in (16,24,72,80,128,136):
        M=ink[y0:y0+16,x0:x0+8].reshape(-1).astype(np.float32)
        nm=int(M.sum())
        if nm<10: continue
        cover = L @ M                     # 每个字形覆盖了多少屏墨
        best=None
        for i in range(0,7168,1):
            need = M * (1.0 - L[i])       # 屏上有、字形 i 没有的墨
            if need.sum()==0:
                best=(0,i,i); break
            add = L @ need
            # 总错配 = 屏墨 - (i|j 覆盖数) + (i|j 多出来的)
            # 近似：先按 add 最大取 j
            j=int(add.argmax())
            union = np.maximum(L[i],L[j])
            mism = np.abs(union-M).sum()
            if best is None or mism<best[0]:
                best=(int(mism),i,j)
        print(f"  {lab} x={x0:3d} 屏墨={nm:3d}  两字并集最小错配={best[0]:3d} gid1={best[1]} gid2={best[2]}")
