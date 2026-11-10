import struct

rom = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()

def thumb_bl_target(pc, h1, h2):
    """计算 Thumb BL 指令目标地址。h1 是第一条半字，h2 是第二条。"""
    # BL 编码：F000-F7FF | F800-FFFF
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

# 检查 0x0802D864 的 bl 目标
h1 = struct.unpack_from('<H', rom, 0x0802D864-0x08000000)[0]
h2 = struct.unpack_from('<H', rom, 0x0802D866-0x08000000)[0]
print(f'0x0802D864: {h1:04X} {h2:04X}')
print(f'BL 目标 = 0x{thumb_bl_target(0x0802D864, h1, h2):08X}')

# 检查 RunTextPrinter 里的递归 bl
h1 = struct.unpack_from('<H', rom, 0x08002E1E-0x08000000)[0]
h2 = struct.unpack_from('<H', rom, 0x08002E20-0x08000000)[0]
print(f'0x08002E1E: {h1:04X} {h2:04X}')
print(f'BL 目标 = 0x{thumb_bl_target(0x08002E1E, h1, h2):08X}')

# 检查 0x0802D844 的 bl（可能是 RunTextPrinter 调用）
for pc in (0x0802D82E, 0x0802D844, 0x0802D85E, 0x0802D864):
    a = pc - 0x08000000
    h1 = struct.unpack_from('<H', rom, a)[0]
    h2 = struct.unpack_from('<H', rom, a+2)[0]
    tgt = thumb_bl_target(pc, h1, h2)
    print(f'0x{pc:08X}: {h1:04X} {h2:04X} -> BL 0x{tgt:08X}')
