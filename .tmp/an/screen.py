import numpy as np
from PIL import Image
SRC=r"C:\Users\Administrator\.workbuddy\clipboard-images\clipboard-2026-09-22T07-18-02-030Z-026cc41b.png"
A=np.asarray(Image.open(SRC).convert('RGB')).astype(int)
S=A[54:54+160]          # 160 行
print("游戏屏 shape",S.shape)
# x 范围：找左右边
print("S[0] 前8像素",[tuple(int(v) for v in p) for p in S[0,:8]])
print("S[0] 后8像素",[tuple(int(v) for v in p) for p in S[0,-8:]])
# 类别
def cls(p):
    r,g,b=p
    if b>200 and r<120 and 100<g<180: return 'T'      # 亮蓝=文字
    if r>230 and g>230 and b>230:     return 'W'      # 白
    if r>60 and r<100 and g>60 and g<95 and b>120: return 'B'   # 窗口蓝底
    if r>120 and g<90 and b<90:       return 'R'      # 亮红
    if r<60 and g<60 and b<70:        return ' '      # 深色底
    if abs(r-g)<12 and abs(g-b)<12:   return '.'      # 灰
    return '?'
lut=np.zeros((256,256,256),dtype='<U1')
def cls_arr(X):
    out=np.empty(X.shape[:2],dtype='<U1')
    r=X[:,:,0];g=X[:,:,1];b=X[:,:,2]
    out[:]='.'
    out[(b>200)&(r<120)&(g>100)&(g<180)]='T'
    out[(r>230)&(g>230)&(b>230)]='W'
    out[(r>60)&(r<100)&(g>60)&(g<95)&(b>120)&(b<170)]='B'
    out[(r>120)&(g<90)&(b<90)]='R'
    out[(r<60)&(g<60)&(b<70)]=' '
    out[(r>60)&(r<100)&(g>20)&(g<40)&(b>20)&(b<40)]='r'
    return out
C=cls_arr(S)
print("类别计数:",{ch:int((C==ch).sum()) for ch in 'TWBRr. ?' if (C==ch).sum()>0})
# T 的行带
t=(C=='T')
rows=t.sum(1)
bands=[];s=None
for i,v in enumerate(rows>0):
    if v and s is None: s=i
    elif not v and s is not None: bands.append((s,i-1)); s=None
if s is not None: bands.append((s,159))
print("亮蓝文字行带:")
for a,b in bands:
    xs=np.where(t[a:b+1].any(0))[0]
    print(f"   y{a:3d}..{b:3d} (h={b-a+1:2d})  x{xs.min():3d}..{xs.max():3d}  n={int(t[a:b+1].sum())}")
