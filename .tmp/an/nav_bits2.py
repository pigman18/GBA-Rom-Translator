import numpy as np
from PIL import Image

im = Image.open(r"C:/Users/Administrator/.workbuddy/clipboard-images/clipboard-2026-09-22T08-09-07-691Z-95ff2422.png").convert("RGB")
a = np.array(im)
sc, ox, oy = 3, 1, 54
game = a[oy:oy+160*sc, ox:ox+240*sc].reshape(160, sc, 240, sc, 3).mean(axis=(1,3))

r,g,b = game[:,:,0], game[:,:,1], game[:,:,2]
blue = (b>150)&(r<120)
blk  = (r<70)&(g<70)&(b<70)

def dump(y0,y1,x0,x1,label):
    print(f"--- {label} rows {y0}..{y1-1} x {x0}..{x1-1} ---")
    hdr = "     " + "".join(str(x%10) for x in range(x0,x1))
    print(hdr)
    for y in range(y0,y1):
        line = "".join('#' if blue[y,x] else ('@' if blk[y,x] else '.') for x in range(x0,x1))
        print(f"{y:4d} {line}")

# 第1行第1列 2 个字形（左上）
dump(24,40,14,34,"row1 col1: 2 glyphs")
# 第2行第1列
dump(40,56,14,34,"row2 col1")

# 数字区（右侧 17:26 附近）
dump(40,56,190,230,"row2 col4 (digits?)")
