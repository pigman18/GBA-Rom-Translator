import numpy as np
from PIL import Image
from collections import Counter
im = Image.open(r"C:/Users/Administrator/.workbuddy/clipboard-images/clipboard-2026-09-22T08-09-07-691Z-95ff2422.png").convert("RGB")
a=np.array(im)
print("shot",a.shape)
best=None
for oy in range(50,62):
  for ox in range(0,5):
    for sc in (3,):
        ys=oy+np.arange(160)*sc
        xs=ox+np.arange(240)*sc
        if ys[-1]>=a.shape[0] or xs[-1]>=a.shape[1]: continue
        g=a[np.ix_(ys,xs)].astype(int)
        c=Counter(map(tuple,g.reshape(-1,3)))
        top=c.most_common(30)
        # 指标：前 12 色覆盖比例
        cov=sum(n for _,n in top[:12])/ (160*240)
        if best is None or cov>best[0]: best=(cov,oy,ox,c)
print("best coverage %.4f  oy=%d ox=%d"%(best[0],best[1],best[2]))
for col,n in best[3].most_common(25): print("   ",col,n)
