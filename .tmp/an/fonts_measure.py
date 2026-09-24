import numpy as np
ROM=open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()
def off(a): return a-0x08000000
NG=7168
# 4bpp 容器：128B = TL(32) BL(32) TR(32) BR(32)
LIBS=[('NORMAL4bpp',0x09000000,128),('SMALL4bpp',0x09100000,128),('MIDDLE4bpp',0x09400000,128),
      ('BIG1bpp',0x09500000,16),('SMALL1bpp',0x09600000,11),('MIDDLE1bpp',0x09700000,13)]
for name,a,sz in LIBS:
    base=off(a)
    if base<0 or base+NG*sz>len(ROM): print(name,"越界"); continue
    L=np.frombuffer(ROM,np.uint8,count=NG*sz,offset=base).reshape(NG,sz)
    ink=(L>0)
    q=[int(ink[:,i*32:(i+1)*32].sum()) for i in range(sz//32)] if sz%32==0 else None
    print(f"== {name} @{a:#010x} stride={sz}")
    if q is not None:
        print("   四象限非零:",q)
    # 取前 300 字，逐行/逐列墨迹占用率
    N=min(NG,400)
    if sz==128:
        # 视为 8 宽 x 16 高 4bpp：上砖 0:32, 下砖 32:64
        rows=np.zeros(16); cols=np.zeros(8)
        for g in range(0,N):
            blk=L[g]
            for half,tb in ((0,0),(1,32)):
                for r in range(8):
                    row=blk[tb+r*4:tb+r*4+4]
                    for ci in range(4):
                        b=row[ci]
                        lo=b&0xF; hi=b>>4
                        if lo: rows[half*8+r]+=1; cols[ci*2]+=1
                        if hi: rows[half*8+r]+=1; cols[ci*2+1]+=1
        print("   行占用:", " ".join(f"{v:4.0f}" for v in rows))
        print("   列占用:", " ".join(f"{v:8.0f}" for v in cols), f"  (样本{N}字)")
        # 有几个字在列 8..15 有墨（即超过 8px 宽）
        over=0
        for g in range(0,N):
            blk=L[g]
            if ink[g, 64:].any(): over+=1
        print(f"   容器后半(64:128)有墨的字数: {over}/{N}")
