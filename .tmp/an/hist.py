import numpy as np
ROM=open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()
def off(a): return a-0x08000000
NG=7168
def nib_hist(base, stride, tile_off, name):
    tot=np.zeros(16,np.int64); colh=np.zeros(16,np.int64); nonempty=0; cnt=0
    for g in range(0,NG,7):     # 采样
        s=base+g*stride
        blk=ROM[s:s+stride]
        if len(blk)<stride: break
        cnt+=1
        ink=0
        for half,tb in ((0,tile_off[0]),(1,tile_off[1])):
            for r in range(8):
                row=blk[tb+r*4:tb+r*4+4]
                for c in range(4):
                    b=row[c]
                    hi=b>>4; lo=b&0xF
                    tot[half*8+r]+= (1 if hi else 0)+(1 if lo else 0)
                    colh[c*2]  += (1 if lo else 0)
                    colh[c*2+1]+= (1 if hi else 0)
                    ink += (1 if hi else 0)+(1 if lo else 0)
        if ink: nonempty+=1
    print(f"[{name}] 采样{cnt} 有墨{nonempty} 行直方图(每行8px×{cnt}):")
    print("   行:", " ".join(f"{v//max(1,cnt):2d}" for v in tot))
    print("   列:", " ".join(f"{v//max(1,cnt):2d}" for v in colh))
base=off(0x09400000)
nib_hist(base,128,(0,32),"MIDDLE stride128 TL,BL")
nib_hist(base,128,(0,64),"MIDDLE stride128 TL,TR")
# 全 ROM 里找 4bpp 128B 结构的候选基址：检查 0x09400000 附近是否真是这结构
print()
print("0x09400000 起 256B:")
print(ROM[base:base+256].hex())
