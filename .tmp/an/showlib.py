import numpy as np
ROM=open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()
def off(a): return a-0x08000000
LIB={'MIDDLE':0x09400000,'SMALL':0x09100000,'NORMAL':0x09000000}
SZ=128
def render(blk,order):
    # order: [TL,BL,TR,BR] 索引
    m=np.zeros((16,16),bool)
    for k,(half,off_) in enumerate([(0,0),(1,32),(0,64),(1,96)]):
        src=blk[off_:off_+32]
        for r in range(8):
            row=src[r*4:r*4+4]
            for c in range(4):
                b=row[c]
                m[half*8+r, c*2]   = (b&0xF)!=0
                m[half*8+r, c*2+1] = (b>>4)!=0
    return m
def show(m,label):
    print("---",label)
    for r in range(16):
        print("   "+"".join("#" if m[r,c] else "." for c in range(16)))
for name,a in LIB.items():
    base=off(a)
    for gid in (467,2389,1512):
        blk=ROM[base+gid*SZ: base+gid*SZ+SZ]
        print(f"===== {name} gid={gid}  首32B={blk[:32].hex()}")
        show(render(blk,None),f"{name}/{gid} 容器序 TL,BL,TR,BR")
        break
    break
# 只渲 MIDDLE 的 3 个字
base=off(LIB['MIDDLE'])
for gid in (467,2389,1512,0,1):
    blk=ROM[base+gid*SZ: base+gid*SZ+SZ]
    print(f"===== MIDDLE gid={gid}")
    show(render(blk,None),f"MIDDLE/{gid}")
