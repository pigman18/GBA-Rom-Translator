import struct
rom = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()

def thumb_bl_target(pc, h1, h2):
    s = (h1 >> 10) & 1; i1=(h2>>13)&1; i2=(h2>>11)&1
    imm10=h1&0x3FF; imm11=h2&0x7FF
    I1=1-(i1^s); I2=1-(i2^s)
    offset=(s<<24)|(I1<<23)|(I2<<22)|(imm10<<12)|(imm11<<1)
    if s: offset-=(1<<25)
    return (pc+4+offset)&0xFFFFFFFF

# 0x08073C18 可能是加载动画表。反汇编它找 ROM 数据表引用。
# 先看它长度，扫 0x08073C18 到 0x08073D00
for pc in range(0x08073C18, 0x08073D00, 2):
    off = pc - 0x08000000
    h1 = struct.unpack_from('<H', rom, off)[0]
    if (h1 & 0xF800) == 0x4800:
        imm = (h1 & 0xFF) * 4
        pc_base = (pc + 4) & ~3
        tgt = pc_base + imm
        w = struct.unpack_from('<I', rom, tgt - 0x08000000)[0]
        if 0x08000000 <= w < 0x09000000:
            print(f'  0x{pc:08X}: ldr @ {tgt:08X} = 0x{w:08X}')
    elif (h1 & 0xF800) == 0xF000:
        h2 = struct.unpack_from('<H', rom, off+2)[0]
        t = thumb_bl_target(pc, h1, h2)
        if 0x08000000 <= t < 0x09000000:
            print(f'  0x{pc:08X}: bl 0x{t:08X}')
