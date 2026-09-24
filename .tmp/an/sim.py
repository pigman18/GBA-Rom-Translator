import numpy as np
ROM=open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()
# GBA 地址 → 文件偏移（ROM 线性映射 0x08000000）
def off(a): return a-0x08000000
LIB_ADDR=0x09400000; NG=7168; SZ=128
base=off(LIB_ADDR)
lib=np.frombuffer(ROM,dtype=np.uint8,count=NG*SZ,offset=base).reshape(NG,SZ)
print("库 @romoff",hex(base),"首字 64B:",lib[0,:64].tobytes().hex())
# nibble 集合
nb=np.unique(np.concatenate([lib[:200]>>4,lib[:200]&0xF]))
print("前200字 nibble 集合:",nb)
# 转 8x16 掩码：TL=0:32, BL=32:64, 每行 4B=8px，左=nibble... 我们只取非零
def to_mask(blk):   # blk = 128B
    m=np.zeros((16,8),bool)
    for half,hb in ((0,0),(1,32)):
        for r in range(8):
            row=blk[hb+r*4: hb+r*4+4]
            for c in range(4):
                b=row[c]
                # 试两种 nibble 次序
                m[half*8+r, c*2]   = (b&0xF)!=0
                m[half*8+r, c*2+1] = (b>>4)!=0
    return m
def to_mask_hl(blk):
    m=np.zeros((16,8),bool)
    for half,hb in ((0,0),(1,32)):
        for r in range(8):
            row=blk[hb+r*4: hb+r*4+4]
            for c in range(4):
                b=row[c]
                m[half*8+r, c*2]   = (b>>4)!=0
                m[half*8+r, c*2+1] = (b&0xF)!=0
    return m
B=np.load('.tmp/zoom3/one_x.npy')
blk=(B[:,:,0]<40)&(B[:,:,1]<40)&(B[:,:,2]<40)
targets={'b1c0':(8,16),'b1c1':(8,24),'b1c2':(8,32),'b3c0':(104,16)}
for name,(y0,x0) in targets.items():
    T=blk[y0:y0+16, x0:x0+8]
    print(f"\n### {name} 屏上墨数={T.sum()}")
    M=np.array([to_mask(lib[g]) for g in range(NG)])
    M2=np.array([to_mask_hl(lib[g]) for g in range(NG)])
    for label,Mx in (("lo=左",M),("hi=左",M2)):
        d=(Mx!=T).sum(axis=(1,2))
        o=np.argsort(d)[:5]
        print(f"  {label}: 最佳5 gid={o.tolist()} d={d[o].tolist()} (满128)")
