import numpy as np
from PIL import Image
SRC=r"C:\Users\Administrator\.workbuddy\clipboard-images\clipboard-2026-09-22T07-18-02-030Z-026cc41b.png"
A=np.asarray(Image.open(SRC).convert('RGB')).astype(int)
H,W,_=A.shape
BG=np.array([79,83,143])
isbg=(np.abs(A-BG).sum(2)<25)
rowfrac=isbg.mean(1); colfrac=isbg.mean(0)
def runs(mask,minlen=3):
    out=[];s=None
    for i,v in enumerate(mask):
        if v and s is None: s=i
        elif not v and s is not None:
            if i-s>=minlen: out.append((s,i-1))
            s=None
    if s is not None: out.append((s,len(mask)-1))
    return out
print("整行都是背景色的行:",runs(rowfrac>0.9))
print("整列都是背景色的列:",runs(colfrac>0.9))
# 内容区
cr=[i for i in range(H) if rowfrac[i]<0.9]
cc=[i for i in range(W) if colfrac[i]<0.9]
print("内容行范围",cr[0],cr[-1],"高",cr[-1]-cr[0]+1)
print("内容列范围",cc[0],cc[-1],"宽",cc[-1]-cc[0]+1)
