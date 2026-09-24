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
    libs[fn[10:19]]=np.array([l4(raw[g*128:g*128+64]) for g in range(len(raw)//128)])

best=None
for oy in range(48,58):
 for ox in range(0,4):
  G=a[np.ix_(oy+np.arange(160)*3, ox+np.arange(240)*3)].astype(int)
  pure_ink  = np.all(G==[33,132,255],axis=2)
  pure_white= np.all(G==[255,255,255],axis=2)
  known = pure_ink|pure_white
  for dy in range(20,32):
   for dx in range(10,24):
     for k in range(6):
        y0,x0=dy,dx+8*k
        S_ink = pure_ink[y0:y0+16, x0:x0+8]
        S_wht = pure_white[y0:y0+16, x0:x0+8]
        K = known[y0:y0+16, x0:x0+8]
        if S_ink.sum()<6 or K.sum()<40: continue
        for name,L in libs.items():
            mis = (L.astype(bool) & S_wht[None,:,:]).sum(axis=(1,2)) + ((~L.astype(bool)) & S_ink[None,:,:]).sum(axis=(1,2))
            gi=int(mis.argmin()); mv=int(mis[gi])
            if best is None or mv<best[0]:
                best=(mv,oy,ox,dy,x0,dx,k,name,gi,int(K.sum()),int(S_ink.sum()))
print("BEST mismatch=%d  oy=%d ox=%d dy=%d x0=%d lib=%s gid=%d known=%d ink=%d"%best)
