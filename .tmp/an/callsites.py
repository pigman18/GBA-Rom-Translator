import struct, capstone, sys
ROM=r"C:/code/GBA-Rom-Translator/roms/origin/POKEMON_RUBY_AXVJ00.gba"
BASE=0x08000000
d=open(ROM,'rb').read()
def se(v,bits):
    if v>>(bits-1): v-=1<<bits
    return v
hits=[]
i=0
while i+4<=len(d):
    h1=struct.unpack_from('<H',d,i)[0]
    if (h1 & 0xF800)==0xF000:
        h2=struct.unpack_from('<H',d,i+2)[0]
        if (h2 & 0xD000)==0xD000:
            S=(h1>>10)&1; imm10=h1&0x3FF
            J1=(h2>>13)&1; J2=(h2>>11)&1; imm11=h2&0x7FF
            I1=1-(J1^S); I2=1-(J2^S)
            off=se((S<<24)|(I1<<23)|(I2<<22)|(imm10<<12)|(imm11<<1),25)
            hits.append((i, BASE+i+4+off)); i+=4; continue
    i+=2
TARGET=0x08002950
md=capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
print(f"### 调 0x08002950 (InitWindowTileData) 的点，各自 r1 值")
for a,t in hits:
    if t!=TARGET: continue
    st=a-24
    code=d[st:a+4]
    lines=[]
    for ins in md.disasm(code, BASE+st):
        lines.append((ins.address, ins.mnemonic, ins.op_str))
    tail=lines[-8:]
    print(f"  调用点 0x{BASE+a:08X}:")
    for ad,m,o in tail: print(f"      0x{ad:08X}  {m:8s} {o}")
