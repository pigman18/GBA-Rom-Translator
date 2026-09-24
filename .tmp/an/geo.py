import numpy as np
from PIL import Image
SRC=r"C:\Users\Administrator\.workbuddy\clipboard-images\clipboard-2026-09-22T07-18-02-030Z-026cc41b.png"
A=np.asarray(Image.open(SRC).convert('RGB')).astype(int)
H,W,_=A.shape
print("png",W,"x",H)
# 逐行/逐列找"非窗口灰"——先看四角与边
print("角像素 左上",A[0,0],"右上",A[0,-1],"左下",A[-1,0],"右下",A[-1,-1])
# 统计主色
u,c=np.unique(A.reshape(-1,3),axis=0,return_counts=True)
o=np.argsort(-c)[:12]
print("主色 top12:")
for i in o: print("   ",tuple(int(v) for v in u[i]),int(c[i]))
# 找左右黑边列
colmean=A.mean(axis=(0,2))
print("列均值 min/max:",colmean.min(),colmean.max())
# 找窗口内容区：与最左列同色的长条
left=A[:,0:3].mean(axis=(0,1))
dark=np.abs(A-A[:,0:1]).sum(2).mean(1)
