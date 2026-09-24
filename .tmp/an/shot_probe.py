import numpy as np
g=np.load(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_native.npy").astype(int)
R,G,B=g[:,:,0],g[:,:,1],g[:,:,2]
ink=(B>200)&(R<120)

print("=== 文本带每行 ink 的 x 区段 ===")
for y in range(22,58):
    xs=np.where(ink[y])[0]
    if len(xs)==0:
        print(f"y={y:3d}  (空)"); continue
    # 分组成连续段（gap>1 断开）
    segs=[]; s=xs[0]; p=xs[0]
    for x in xs[1:]:
        if x>p+1: segs.append((s,p)); s=x
        p=x
    segs.append((s,p))
    print(f"y={y:3d}  " + "  ".join(f"{a}..{b}" for a,b in segs))
