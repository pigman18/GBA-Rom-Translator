import struct, capstone
ROM=r"C:/code/GBA-Rom-Translator/roms/origin/POKEMON_RUBY_AXVJ00.gba"
BASE=0x08000000
d=open(ROM,'rb').read()
n=len(d)
# 收集所有 bl 目标
hits=[]
i=0
def se(v,bits):
    if v>>(bits-1): v-=1<<bits
    return v
while i+4<=n:
    h1=struct.unpack_from('<H',d,i)[0]
    if (h1 & 0xF800)==0xF000:
        h2=struct.unpack_from('<H',d,i+2)[0]
        if (h2 & 0xD000)==0xD000:      # BL (not BLX)
            S=(h1>>10)&1; imm10=h1&0x3FF
            J1=(h2>>13)&1; J2=(h2>>11)&1; imm11=h2&0x7FF
            I1=1-(J1^S); I2=1-(J2^S)
            off=se((S<<24)|(I1<<23)|(I2<<22)|(imm10<<12)|(imm11<<1),25)
            tgt=BASE+i+4+off
            hits.append((i, tgt))
            i+=4; continue
    i+=2
print("total BL:", len(hits))
want={0x08002950:"InitWindowTileData(win,startOffset)",
      0x08002A50:"LoadGlyph(font0/3)",
      0x080029E0:"PrefetchWorker",
      0x08002BD0:"tm3 loader"}
for a,t in hits:
    if t in want:
        print("  call @0x%08X -> 0x%08X %s"%(BASE+a,t,want[t]))
