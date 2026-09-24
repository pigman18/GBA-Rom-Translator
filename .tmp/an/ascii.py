import numpy as np
from PIL import Image
SRC=r"C:\Users\Administrator\.workbuddy\clipboard-images\clipboard-2026-09-22T07-18-02-030Z-026cc41b.png"
A=np.asarray(Image.open(SRC).convert('RGB')).astype(int)
H,W,_=A.shape
# 找标题栏(53,53,53)/菜单栏(白) 与 游戏内容的分界
for y in range(H):
    row=A[y]
    u=np.unique(row,axis=0)
    if len(u)<=3 and 30<u[0][0]<80:
        pass
# 打印每行的主色
prev=None
for y in range(H):
    u,c=np.unique(A[y],axis=0,return_counts=True)
    o=np.argsort(-c)
    t=tuple(int(v) for v in u[o[0]])
    if t!=prev:
        print(f"y{y:3d} 主色 {t}  ({c[o[0]]}/{W})")
        prev=t
