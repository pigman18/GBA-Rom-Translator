import struct
rom = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()

def thumb_bl_target(pc, h1, h2):
    s=(h1>>10)&1; i1=(h2>>13)&1; i2=(h2>>11)&1
    imm10=h1&0x3FF; imm11=h2&0x7FF
    I1=1-(i1^s); I2=1-(i2^s)
    offset=(s<<24)|(I1<<23)|(I2<<22)|(imm10<<12)|(imm11<<1)
    if s: offset-=(1<<25)
    return (pc+4+offset)&0xFFFFFFFF

# ProcessCurrentChar @ 0x080032F8，反汇编带注释
pc = 0x080032F8
end = 0x08003380
while pc < end:
    off = pc - 0x08000000
    h1 = struct.unpack_from('<H', rom, off)[0]
    cmt = ''
    if (h1 & 0xF800) == 0xF000:
        h2 = struct.unpack_from('<H', rom, off+2)[0]
        cmt = f'  ; bl 0x{thumb_bl_target(pc,h1,h2):08X}'
    elif h1 == 0x4687:
        cmt = '  ; mov pc, r3 (跳转表跳转)'
    elif h1 == 0xBC02:
        cmt = '  ; pop {pc}'
    elif h1 == 0x4708:
        cmt = '  ; bx r1'
    print(f'  0x{pc:08X}: {h1:04X}{cmt}')
    pc += 2
