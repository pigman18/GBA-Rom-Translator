import numpy as np, os
from PIL import Image
FD=r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/graphic/fonts"
im = Image.open(r"C:/Users/Administrator/.workbuddy/clipboard-images/clipboard-2026-09-22T08-09-07-691Z-95ff2422.png").convert("RGB")
a=np.array(im)

def l4(b64):
    out=np.zeros((16,8),np.uint8)
    for i in range(64):
        b=b64[i]; row=i//4; cb=(i%4)*2
        if b&0x0F: out[row,cb]=1
        if b&0xF0: out[row,cb+1]=1
    return out

libs={}
for fn in ("PokeRSFontChsMiddle_unshadow(0xE0000).bin","PokeRSFontChsNormal_unshadow(0xE0000).bin","PokeRSFontChsSmall_unshadow(0xE0000).bin"):
    raw=open(os.path.join(FD,fn),'rb').read()
    L=np.array([l4(raw[g*128:g*128+64]) for g in range(len(raw)//128)])
    libs[fn[10:19]]=(L.reshape(len(L),128).astype(np.float32), L.reshape(len(L),128).astype(np.int16))

oy,ox=51,1
G=a[np.ix_(oy+np.arange(160)*3, ox+np.arange(240)*3)].astype(int)
pure_ink  = np.all(G==[33,132,255],axis=2)
pure_white= np.all(G==[255,255,255],axis=2)

res=[]
for dy in range(22,30):
 for dx in range(12,22):
  for k in range(6):
    y0,x0=dy,dx+8*k
    si=pure_ink[y0:y0+16,x0:x0+8]; sw=pure_white[y0:y0+16,x0:x0+8]
    if si.sum()<6: continue
    si=si.reshape(128); sw=sw.reshape(128)
    for name,(Lf,Li) in libs.items():
        mis = Lf.dot(sw.astype(np.float32)) + (1.0-Lf).dot(si.astype(np.float32))
        gi=int(mis.argmin()); mv=float(mis[gi])
        res.append((mv,dy,x0,name,gi,int(si.sum())))
res.sort()
print("TOP 25 (mismatch, dy, x0, lib, gid, inkpx):")
for r in res[:25]: print("   %.0f  dy=%d x0=%d %s gid=%d ink=%d"%r)
