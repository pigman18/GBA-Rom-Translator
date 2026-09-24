import numpy as np
from PIL import Image
im = Image.open(r"C:/Users/Administrator/.workbuddy/clipboard-images/clipboard-2026-09-22T08-09-07-691Z-95ff2422.png").convert("RGB")
a=np.array(im)
oy,ox,sc=51,1,3
g=a[np.ix_(oy+np.arange(160)*sc, ox+np.arange(240)*sc)].astype(int)

def cls(p):
    R,G,B=p
    if R>200 and G>200 and B>200: return '.'      # 白底
    if B>180 and R<100: return '#'                # 纯蓝 ink
    if B>180 and R<170: return '+'                # 半蓝（重采样边缘）
    if abs(R-G)<20 and abs(G-B)<20 and 90<R<200:  return 'g'  # 灰
    if R>90 and G<90: return 'r'                  # 红框
    if R<70 and G<70 and B<70: return '@'         # 黑
    return '?'

def dump(y0,y1,x0,x1):
    print("      "+"".join(str(x//10%10) for x in range(x0,x1)))
    print("      "+"".join(str(x%10) for x in range(x0,x1)))
    for y in range(y0,y1):
        print(f"{y:4d}  "+"".join(cls(g[y,x]) for x in range(x0,x1)))

print("===== 白框文字区 x 10..74, rows 22..58 =====")
dump(22,58,10,74)
