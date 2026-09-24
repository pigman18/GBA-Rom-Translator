import numpy as np
from PIL import Image
SRC=r"C:/Users/Administrator/.workbuddy/clipboard-images/clipboard-2026-09-22T06-21-45-660Z-c7440486.png"
im=Image.open(SRC).convert('RGB'); A=np.asarray(im).astype(int)
H,W,_=A.shape
desk=(np.abs(A[:,:,0]-79)<10)&(np.abs(A[:,:,1]-83)<10)&(np.abs(A[:,:,2]-143)<10)
# 只看 y>30 避开标题栏
sub=desk[30:,:]
rows=sub.mean(1); cols=desk[30:,:].mean(0)
ry=np.where(rows<0.5)[0]+30
rx=np.where(cols<0.5)[0]
print("非桌面行范围",ry.min(),ry.max(),"高",ry.max()-ry.min()+1)
print("非桌面列范围",rx.min(),rx.max(),"宽",rx.max()-rx.min()+1)
# 打印行剖面（找连续块）
def runs(mask):
    out=[];s=None
    for i,v in enumerate(mask):
        if v and s is None: s=i
        elif not v and s is not None: out.append((s,i-1)); s=None
    if s is not None: out.append((s,len(mask)-1))
    return out
print("行块:",[ (a+30,b+30) for a,b in runs(rows<0.5)])
print("列块:",runs(cols<0.5))
