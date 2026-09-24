import numpy as np, os, itertools
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
L=np.array([l4(raw[i*128:i*128+64]) for i in range(7168)])   # (7168,16,8)

def colvecs(M):
    return tuple(sorted(tuple(int(M[r,c]) for r in range(16)) for c in range(8)))
def rowvecs(M):
    return tuple(sorted(tuple(int(M[r,c]) for c in range(8)) for r in range(16)))

LibCols=[colvecs(L[i]) for i in range(7168)]
LibRows=[rowvecs(L[i]) for i in range(7168)]

print("### 屏幕格 vs 库字形：列/行多重集一致（⇒ 只是行列置换）")
for (y0,lab) in ((24,"row1"),(40,"row2")):
    for x0 in (16,24,72,80,128,136):
        M=ink[y0:y0+16,x0:x0+8]
        if M.sum()<10: continue
        c=colvecs(M); r=rowvecs(M)
        cm=[i for i in range(7168) if LibCols[i]==c]
        rm=[i for i in range(7168) if LibRows[i]==r]
        print(f"  {lab} x={x0:3d} 列多集命中 {len(cm)} 个 gid {cm[:6]}   行多集命中 {len(rm)} 个 gid {rm[:6]}")
