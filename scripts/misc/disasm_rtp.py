import struct
rom = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()

def thumb_bl_target(pc, h1, h2):
    s  = (h1 >> 10) & 1
    i1 = (h2 >> 13) & 1
    i2 = (h2 >> 11) & 1
    imm10 = h1 & 0x3FF
    imm11 = h2 & 0x7FF
    I1 = 1 - (i1 ^ s)
    I2 = 1 - (i2 ^ s)
    offset = (s << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
    if s:
        offset -= (1 << 25)
    return (pc + 4 + offset) & 0xFFFFFFFF

# 完整反汇编 RunTextPrinter (0x08002DE8) 到 0x08002E38，带 BL 解析
pc = 0x08002DE8
end = 0x08002E40
while pc < end:
    a = pc - 0x08000000
    h1 = struct.unpack_from('<H', rom, a)[0]
    comment = ''
    # 检测 BL (F000-F7FF, F800-FFFF)
    if (h1 & 0xF800) == 0xF000:
        h2 = struct.unpack_from('<H', rom, a+2)[0]
        tgt = thumb_bl_target(pc, h1, h2)
        comment = f'  ; bl 0x{tgt:08X}'
    # 检测 bx
    elif h1 == 0x4700:
        comment = '  ; bx r0'
    elif h1 == 0x4708:
        comment = '  ; bx r1'
    elif h1 == 0x4710:
        comment = '  ; bx r2'
    elif h1 == 0x4718:
        comment = '  ; bx r3'
    # pop {pc}
    elif h1 == 0xBC02:
        comment = '  ; pop {pc}'
    elif h1 == 0xBD00:
        comment = '  ; pop {pc} (wide)'

    print(f'  0x{pc:08X}: {h1:04X}{comment}')
    pc += 2
