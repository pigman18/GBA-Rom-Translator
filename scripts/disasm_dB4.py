import struct
rom = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()

def thumb_bl_target(pc, h1, h2):
    s  = (h1 >> 10) & 1
    i1 = (h2 >> 13) & 1
    i2 = (h2 >> 11) & 1
    imm10 = h1 & 0x3FF
    imm11 = h2 & 0x7FF
    I1 = 1 - (i1 ^ s); I2 = 1 - (i2 ^ s)
    offset = (s << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
    if s: offset -= (1 << 25)
    return (pc + 4 + offset) & 0xFFFFFFFF

def disasm(addr, count):
    pc = addr & ~1
    for i in range(count):
        a = pc - 0x08000000
        if a+1 >= len(rom): break
        h = struct.unpack_from('<H', rom, a)[0]
        cmt = ''
        if (h & 0xF800) == 0xF000:
            h2 = struct.unpack_from('<H', rom, a+2)[0]
            cmt = f'  ; bl 0x{thumb_bl_target(pc,h,h2):08X}'
        elif h == 0x4700: cmt = '  ; bx r0'
        elif h == 0x4708: cmt = '  ; bx r1'
        elif h == 0x4710: cmt = '  ; bx r2'
        elif h == 0x4718: cmt = '  ; bx r3'
        elif h == 0xBC02: cmt = '  ; pop {pc}'
        elif h == 0x4687: cmt = '  ; mov pc, r3'
        print(f'  0x{pc:08X}: {h:04X}{cmt}')
        pc += 2

print("=== 0x08002DB4（RunTextPrinter 调用的子函数）===")
disasm(0x08002DB4, 30)
