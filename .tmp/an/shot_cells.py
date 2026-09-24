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

libs={}
for fn in ("PokeRSFontChsMiddle_unshadow(0xE0000).bin","PokeRSFontChsNormal_unshadow(0xE0000).bin","PokeRSFontChsSmall_unshadow(0xE0000).bin"):
    raw=open(os.path.join(FD,fn),'rb').read()
    libs[fn[10:16]]=np.array([l4(raw[i*128:i*128+64]) for i in range(len(raw)//128)])
for k,v in libs.items(): print(k, v.shape)

R,G,B = g[:,:,0],g[:,:,1],g[:,:,2]
ink  = (B>200)&(R<120)
whit = (R>200)&(G>200)&(B>200)

def cellmask(y0,x0):
    return ink[y0:y0+16, x0:x0+8]

def show(m,label):
    print("   "+label)
    for r in range(16):
        print("     "+"".join('#' if m[r,c] else '.' for c in range(8)))

for (y0,label) in ((8,"title"),(24,"row1"),(40,"row2")):
    print(f"\n########## {label}  y0={y0} ##########")
    for k in range(28):
        x0=16+8*k
        if x0+8>236: break
        m=cellmask(y0,x0)
        n=int(m.sum())
        if n==0: continue
        best=None
        for name,L in libs.items():
            d=(L!=m[None,:,:]).sum(axis=(1,2))
            i=int(d.argmin())
            if best is None or d[i]<best[0]: best=(int(d[i]),name,i,int(L[i].sum()))
        d,name,gid,libink=best
        tag = "OK" if d==0 else ("~" if d<=3 else "X")
        print(f"  col{k:2d} x={x0:3d} ink={n:3d}  best={name} gid={gid:5d} d={d:3d} libink={libink:3d}  {tag}")
