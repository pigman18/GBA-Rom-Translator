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
# 打包成 128 bit：两个 u64
def pack(M):
    flat=M.reshape(-1)
    a=np.zeros(len(M),np.uint64); b=np.zeros(len(M),np.uint64)
    for k in range(64):
        if flat.shape[1] if flat.ndim>1 else 0: pass
    # 手工
    for k in range(64):
        col=k
        a |= (flat[:,k].astype(np.uint64) << np.uint64(k))
    for k in range(64,128):
        b |= (flat[:,k].astype(np.uint64) << np.uint64(k-64))
    return a,b
La,Lb=pack(L)
pop=lambda x: np.array([bin(int(v)).count('1') for v in x])

for (y0,lab) in ((24,"row1"),(40,"row2")):
    for x0 in (16,24,72,80,128,136):
        M=ink[y0:y0+16,x0:x0+8]
        if M.sum()<10: continue
        Ma,Mb=pack(M[None,:,:]); Ma=Ma[0]; Mb=Mb[0]
        inv_a=~Ma; inv_b=~Mb
        best=None
        for i in range(7168):
            na=(La[i]&inv_a); nb=(Lb[i]&inv_b)
            # 剩余未覆盖
            ra=(Ma&~La[i]); rb=(Mb&~Lb[i])
            cov=(La & np.uint64(ra)) ; cov2=(Lb & np.uint64(rb))
            ca=np.array([bin(int(v)).count('1') for v in cov])
            cb=np.array([bin(int(v)).count('1') for v in cov2])
            j=int((ca+cb).argmax())
            rem=bin(int(ra & ~La[j])).count('1')+bin(int(rb & ~Lb[j])).count('1')
            extra=bin(int((La[j]|Lb[j]) if False else (La[j]&(~Ma)))).count('1')+0
            tot=rem
            if best is None or tot<best[0]: best=(tot,i,j)
        print(f"  {lab} x={x0:3d} 屏墨={int(M.sum()):3d}  两字并集最小未覆盖={best[0]:3d} gid1={best[1]} gid2={best[2]}")
