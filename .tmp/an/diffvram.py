import numpy as np
def ld(p): return np.frombuffer(open(p,'rb').read(),np.uint8)
a=ld('.tmp/drive_o_sum_vram.bin'); b=ld('.tmp/drive_v_sum_vram.bin')
print("len",len(a),len(b))
d=(a!=b).reshape(-1,32).any(1)
idx=np.where(d)[0]
print("差异砖数",len(idx))
# 按 16KB 块统计
for blk in range(6):
    n=((idx>=blk*512)&(idx<(blk+1)*512)).sum()
    print(f"  blk{blk}: {n}")
print("前 60 个差异砖:",[int(i) for i in idx[:60]])
