import numpy as np
from collections import Counter
g=np.load(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_native.npy").astype(int)
def hist(y0,y1,x0,x1,lbl):
    reg=g[y0:y1,x0:x1]
    c=Counter(map(tuple,reg.reshape(-1,3)))
    print(f"--- {lbl} y{y0}..{y1-1} x{x0}..{x1-1}  ({reg.shape[0]*reg.shape[1]} px)")
    for col,n in c.most_common(12): print("      ",col,n)
hist(24,40,16,64,"row1 左半（第1-6格）")
hist(40,56,16,64,"row2 左半")
hist(24,40,184,232,"row1 右端（数字区）")
# 放宽 ink 统计
R,G,B=g[:,:,0],g[:,:,1],g[:,:,2]
loose=(B>150)&(R<160)
print("loose ink px:", int(loose.sum()), " exact-blue px:", int((np.all(g==[33,132,255],axis=2)).sum()))
print("loose 各行:", [(y,int(loose[y].sum())) for y in range(24,56) if loose[y].sum()>0][:20])
