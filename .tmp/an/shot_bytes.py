import numpy as np
g=np.load(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_native.npy").astype(int)
ink=np.all(g==[33,132,255],axis=2)

def tile_bytes(m):   # m: 8x8 bool
    out=[]
    for r in range(8):
        for c in (0,2,4,6):
            hi = 1 if m[r,c] else 0
            lo = 1 if m[r,c+1] else 0
            out.append((hi<<4)|lo)   # 高 nibble=左像素, 低 nibble=右像素
    return bytes(out)

print("### 屏幕砖的 4bpp 字节（高nibble=左像素）")
for (y0,lab) in ((24,"row1"),(40,"row2")):
    for x0 in (16,24,72,80,128,136,208,216):
        m=ink[y0:y0+16,x0:x0+8]
        if m.sum()<3: continue
        for tag,t in (("上",m[0:8,:]),("下",m[8:16,:])):
            b=tile_bytes(t)
            hx=" ".join(f"{x:02X}" for x in b)
            # 显示 nibble 串
            nib="".join(f"{x:x}" for x in b)
            print(f"  {lab} x={x0:3d} {tag}: {hx}")
            print(f"                    {nib}")
