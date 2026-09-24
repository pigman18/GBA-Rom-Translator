import numpy as np
from PIL import Image
SRC=r"C:/Users/Administrator/.workbuddy/clipboard-images/clipboard-2026-09-22T06-21-45-660Z-c7440486.png"
A=np.asarray(Image.open(SRC).convert('RGB')).astype(int)
H,W,_=A.shape
red=(A[:,:,0]>150)&(A[:,:,1]<90)&(A[:,:,2]<90)
print("red px",red.sum())
rr=np.where(red.any(1))[0]; rc=np.where(red.any(0))[0]
print("红框 行",rr.min(),rr.max(),"列",rc.min(),rc.max())
# 行/列剖面
rws=red.sum(1); cls=red.sum(0)
top=[i for i in range(H) if rws[i]>200]
print("强红行:",top[:6],"...",top[-6:] if len(top)>6 else "")
# 找最外圈红框：第一条强红行 / 最后一条
# GBA 视口 = 红框内侧
# 试：外框 y0=rr.min(), y1=rr.max(); x0=rc.min(), x1=rc.max()
h=rr.max()-rr.min()+1; w=rc.max()-rc.min()+1
print("外框尺寸",w,"x",h, "→ /3:",w/3,h/3)
# 内容区（不含边框像素）：边框厚约 9px(3x3)
