import numpy as np
from PIL import Image
SRC=r"C:/Users/Administrator/.workbuddy/clipboard-images/clipboard-2026-09-22T06-21-45-660Z-c7440486.png"
A=np.asarray(Image.open(SRC).convert('RGB'))
# 1x
B=A[54:54+480:3, 1:1+720:3]
def cellcols(y0,x0):
    C=B[y0:y0+16, x0:x0+8].reshape(-1,3)
    u,c=np.unique(C,axis=0,return_counts=True)
    return sorted(zip(c.tolist(),[tuple(int(v) for v in x) for x in u]),reverse=True)
print("黑带1字0 (y8,x16):")
for n,col in cellcols(8,16)[:6]: print("   ",col,n)
print("黑带2字0 (y72,x16):")
for n,col in cellcols(72,16)[:6]: print("   ",col,n)
print("蓝带1字0 (y24,x16):")
for n,col in cellcols(24,16)[:6]: print("   ",col,n)
print("蓝'17:26'处 (y24,x168):")
for n,col in cellcols(24,168)[:6]: print("   ",col,n)
