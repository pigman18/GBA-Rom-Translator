import numpy as np
g=np.load(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_native.npy").astype(int)

def cls(p):
    R,G,B=p
    if R>200 and G>200 and B>200: return '.'
    if B>200 and R<120: return '#'          # 蓝 ink
    if R>200 and G<120 and B<120: return 'r' # 红
    if R<60 and G<60 and B<60: return '@'    # 黑
    return '?'

print("=== 整屏 240x160 概览（每 1 行 1 行）===")
print("      "+"".join(str(x//10%10) for x in range(0,240,1))[:0])
for y in range(160):
    print(f"{y:4d}  "+"".join(cls(g[y,x]) for x in range(240)))
