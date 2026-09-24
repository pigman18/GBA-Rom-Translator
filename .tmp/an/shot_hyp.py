import numpy as np, os
g=np.load(r"C:/code/GBA-Rom-Translator/.tmp/an/shot_native.npy").astype(int)
ink=np.all(g==[33,132,255],axis=2)
FD=r"C:/code/GBA-Rom-Translator/work/POKEMON_RUBY_AXVJ00/graphic/fonts"
def brick(b32):
    m=np.zeros((8,8),bool)
    for i in range(32):
        b=b32[i]; r=i//4; cb=(i%4)*2
        if b&0x0F: m[r,cb]=True
        if b&0xF0: m[r,cb+1]=True
    return m
raw=open(os.path.join(FD,"PokeRSFontChsMiddle_unshadow(0xE0000).bin"),'rb').read()
A=np.array([brick(raw[i*128:i*128+32]) for i in range(7168)])       # 块0
B=np.array([brick(raw[i*128+32:i*128+64]) for i in range(7168)])    # 块1

# 假设1：竖叠（上=A, 下=B）—— 现行 engine.c
# 假设2：横排（左=A, 右=B）—— 若容器是 16 宽 x 8 高
print("=== 假设1 竖叠（上=块0,下=块1）最佳 d ===")
best=[]
for dy in range(22,46):
  for dx in range(12,232):
    if dy+16>160 or dx+8>240: continue
    t=ink[dy:dy+8,dx:dx+8]; b=ink[dy+8:dy+16,dx:dx+8]
    if t.sum()+b.sum()<10: continue
    d=(A!=t[None,:,:]).sum(axis=(1,2)) + (B!=b[None,:,:]).sum(axis=(1,2))
    i=int(d.argmin()); best.append((int(d[i]),dy,dx,i,int(t.sum()+b.sum())))
best.sort()
for r in best[:8]: print(f"   d={r[0]:3d} dy={r[1]} dx={r[2]} gid={r[3]:5d} 屏墨={r[4]}")

print("\n=== 假设2 横排（左=块0,右=块1）最佳 d ===")
best=[]
for dy in range(22,46):
  for dx in range(12,232,1):
    if dy+8>160 or dx+16>240: continue
    l=ink[dy:dy+8,dx:dx+8]; r=ink[dy:dy+8,dx+8:dx+16]
    if l.sum()+r.sum()<10: continue
    d=(A!=l[None,:,:]).sum(axis=(1,2)) + (B!=r[None,:,:]).sum(axis=(1,2))
    i=int(d.argmin()); best.append((int(d[i]),dy,dx,i,int(l.sum()+r.sum())))
best.sort()
for r in best[:8]: print(f"   d={r[0]:3d} dy={r[1]} dx={r[2]} gid={r[3]:5d} 屏墨={r[4]}")
