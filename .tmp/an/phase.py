import numpy as np
from PIL import Image
SRC=r"C:/Users/Administrator/.workbuddy/clipboard-images/clipboard-2026-09-22T06-21-45-660Z-c7440486.png"
A=np.asarray(Image.open(SRC).convert('RGB')).astype(np.int16)
H,W,_=A.shape
best=None
for x0 in range(0,6):
  for y0 in range(50,60):
    for s in (3,):
        w=(W-x0)//s; h=(H-y0)//s
        if w<240 or h<160: continue
        C=A[y0:y0+h*s, x0:x0+w*s].reshape(h,s,w,s,3)
        # 每块内极差
        rng=C.max(axis=(1,3))-C.min(axis=(1,3))
        bad=(rng.max(axis=2)>12).mean()
        if best is None or bad<best[0]: best=(bad,x0,y0,s)
print("最佳块一致性: bad_ratio=%.5f  x0=%d y0=%d s=%d"%best)
# 检查 s=2,4
for s in (2,4):
    b=None
    for x0 in range(0,4):
      for y0 in range(52,58):
        w=(W-x0)//s; h=(H-y0)//s
        if w<240 or h<160: continue
        C=A[y0:y0+h*s, x0:x0+w*s].reshape(h,s,w,s,3)
        rng=C.max(axis=(1,3))-C.min(axis=(1,3))
        bad=(rng.max(axis=2)>12).mean()
        if b is None or bad<b[0]: b=(bad,x0,y0,s)
    print("s=%d 最佳 bad_ratio=%.5f x0=%d y0=%d"%(s,b[0],b[1],b[2]))
