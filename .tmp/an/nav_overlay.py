import numpy as np
from PIL import Image
im = Image.open(r"C:/Users/Administrator/.workbuddy/clipboard-images/clipboard-2026-09-22T08-09-07-691Z-95ff2422.png").convert("RGB")
a=np.array(im)
oy,ox,sc=51,1,3
g=a[np.ix_(oy+np.arange(160)*sc, ox+np.arange(240)*sc)].astype(np.uint8)

# 二值化：ink = 纯蓝 (33,132,255)；其余视为背景
ink = np.all(g==[33,132,255],axis=2)
print("pure-blue px:", int(ink.sum()))
# 每行/每列墨量
rows=ink.sum(axis=1); cols=ink.sum(axis=0)
print("ink rows:", [ (y,int(rows[y])) for y in range(160) if rows[y]>0 ])
print("ink cols:", [ (x,int(cols[x])) for x in range(240) if cols[x]>0 ])

# 白框文字区放大 6 倍 + 网格
Z=6
crop=g[20:60, 8:80].astype(np.uint8)
big=np.repeat(np.repeat(crop,Z,axis=0),Z,axis=1).copy()
# 网格：垂直每 8px（自 x=16），水平每 16px（自 y=25）
for x in range(16,80,8):
    if x-8>=0:
        px=(x-8)*Z
        if px < big.shape[1]: big[:,px]=[255,0,0]
for y in range(25,60,16):
    py=(y-20)*Z
    if 0<=py<big.shape[0]: big[py,:]=[0,200,0]
Image.fromarray(big).save(r"C:/code/GBA-Rom-Translator/.tmp/an/nav_grid_overlay.png")
print("saved nav_grid_overlay.png", big.shape)
