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

# sub_802D798 里所有 bl 目标
bls = [
    0x0802D7EA, 0x0802D7FE, 0x0802D81E, 0x0802D824,
    0x0802D82E, 0x0802D844, 0x0802D84A, 0x0802D85E, 0x0802D864,
]
for pc in bls:
    a = pc - 0x08000000
    h1 = struct.unpack_from('<H', rom, a)[0]
    h2 = struct.unpack_from('<H', rom, a+2)[0]
    tgt = thumb_bl_target(pc, h1, h2)
    print(f'0x{pc:08X}: {h1:04X} {h2:04X} -> bl 0x{tgt:08X}')
