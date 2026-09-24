import numpy as np
from collections import Counter
g=np.load(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_native.npy").astype(int)
def hist(y0,y1,x0,x1,lbl):
    reg=g[y0:y1,x0:x1]
    c=Counter(map(tuple,reg.reshape(-1,3)))
    tot=reg.shape[0]*reg.shape[1]
    print(f"--- {lbl} y{y0}..{y1-1} x{x0}..{x1-1}")
    for col,n in c.most_common(8):
        print(f"      {col}  {n:5d}  {100*n/tot:5.1f}%")
hist(24,40,64,96,"row1 第7-8格 x64..95")
hist(40,56,72,104,"row2 x72..103")
hist(24,40,16,64,"row1 左半 x16..63")
print()
R,G,B=g[:,:,0],g[:,:,1],g[:,:,2]
print("全屏各色像素数（>0.05%）：")
c=Counter(map(tuple,g.reshape(-1,3)))
for col,n in c.most_common(30):
    if n> 240*160*0.0005:
        print(f"   {col}  {n}")
