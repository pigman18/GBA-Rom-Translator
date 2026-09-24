import numpy as np
from PIL import Image
from collections import Counter
p = r"C:/Users/Administrator/.workbuddy/clipboard-images/clipboard-2026-09-22T08-34-54-307Z-4d6b3feb.png"
a = np.array(Image.open(p).convert("RGB")).astype(int)
print("shot", a.shape)

# 找游戏视口：242 宽含 1px 边；高 215，视口 160 ⇒ oy = 215-160 = 55
best=None
for oy in range(50,60):
  for ox in range(0,3):
    if oy+160>a.shape[0] or ox+240>a.shape[1]: continue
    g=a[oy:oy+160, ox:ox+240]
    c=Counter(map(tuple, g.reshape(-1,3)))
    top=c.most_common(16)
    cov=sum(n for _,n in top)/ (160*240)
    if best is None or cov>best[0]: best=(cov,oy,ox,top)
print("best coverage %.4f oy=%d ox=%d"%(best[0],best[1],best[2]))
for col,n in best[3]: print("   ",col,n)
oy,ox=best[1],best[2]
g=a[oy:oy+160, ox:ox+240].astype(np.uint8)
np.save(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_native.npy", g)
big=np.repeat(np.repeat(g,5,axis=0),5,axis=1)
Image.fromarray(big).save(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_native_x5.png")
print("saved", big.shape)
