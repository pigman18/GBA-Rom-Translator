import numpy as np
from PIL import Image
from collections import Counter
im = Image.open(r"C:/Users/Administrator/.workbuddy/clipboard-images/clipboard-2026-09-22T08-09-07-691Z-95ff2422.png").convert("RGB")
a=np.array(im)
sc,ox,oy=3,1,55
game=a[oy:oy+480, ox:ox+720].reshape(160,sc,240,sc,3).mean(axis=(1,3))
reg=game[24:40,12:40]
c=Counter(map(tuple, reg.reshape(-1,3).round().astype(int)))
print("band A region top colors:")
for col,n in c.most_common(15): print("  ",col,n)
print()
# 打印该区域每像素亮度分类
r,g,b=game[:,:,0],game[:,:,1],game[:,:,2]
print("region rows 24..39, x 12..39  (char: B=蓝 W=白 G=灰 ?=其它)")
for y in range(24,40):
    line=""
    for x in range(12,40):
        R,G,B=game[y,x]
        if R>200 and G>200 and B>200: line+="W"
        elif B>140 and R<130: line+="B"
        elif abs(R-G)<25 and abs(G-B)<25 and 100<R<200: line+="G"
        else: line+=f"?{int(R):03d},{int(G):03d},{int(B):03d}?"
    print(f"{y:3d} {line}")
