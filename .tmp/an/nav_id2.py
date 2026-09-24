import numpy as np, os
from PIL import Image
FD = r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/graphic/fonts"
im = Image.open(r"C:/Users/Administrator/.workbuddy/clipboard-images/clipboard-2026-09-22T08-09-07-691Z-95ff2422.png").convert("RGB")
a=np.array(im)

def l4(b64):
    v=0
    for i in range(64):
        b=b64[i]; row=i//4; cb=(i%4)*2
        if b&0x0F: v|=1<<(row*8+cb)
        if b&0xF0: v|=1<<(row*8+cb+1)
    return v

libs={}
for fn in ("PokeRSFontChsMiddle_unshadow(0xE0000).bin","PokeRSFontChsNormal_unshadow(0xE0000).bin","PokeRSFontChsSmall_unshadow(0xE0000).bin"):
    p=os.path.join(FD,fn); raw=open(p,'rb').read(); n=len(raw)//128
    libs[fn.split('_')[0][10:]] = [l4(raw[g*128:g*128+64]) for g in range(n)]
for k,v in libs.items(): print(k, len(v))

best=None
for oy in range(48,58):
  for ox in range(0,4):
    G=a[np.ix_(oy+np.arange(160)*3, ox+np.arange(240)*3)].astype(int)
    R=G[:,:,0]; B=G[:,:,2]
    M=(R<144)&(B>150)
    for dy in range(20,30):
      for dx in range(10,22):
        # 4 个格子：第1文字行 x dx..dx+31
        tot=0; det=[]
        for k in range(4):
            v=0
            for r in range(16):
                for c in range(8):
                    if M[dy+r, dx+8*k+c]: v|=1<<(r*8+c)
            if v==0: det.append((999,None)); tot+=600; continue
            bd=999; bn=-1
            for name,gl in libs.items():
                for gi,gv in enumerate(gl):
                    d=(v^gv).bit_count()
                    if d<bd: bd=d; bn=(name,gi)
            det.append((bd,bn)); tot+=bd
        if best is None or tot<best[0]:
            best=(tot,oy,ox,dy,dx,det)
print("BEST total=%d  oy=%d ox=%d dy=%d dx=%d"%best[:5])
for i,d in enumerate(best[5]): print("   cell",i,d)
