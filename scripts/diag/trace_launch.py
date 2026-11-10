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

# 日版 LaunchBattleAnimation @ 0x08072770，长度英文版 0x1b0=432，但日版可能不同。
# 扫到 0x08072920（之前看到是函数边界）
start = 0x08072770
end = 0x08072920

# 收集所有 bl 目标（ROM 8xxxxxxx）和 ldr 字面量（ROM 8xxxxxxx 数据）
bl_targets = set()
ldr_rom = set()
for pc in range(start, end, 2):
    off = pc - 0x08000000
    h1 = struct.unpack_from('<H', rom, off)[0]
    if (h1 & 0xF800) == 0xF000:
        h2 = struct.unpack_from('<H', rom, off+2)[0]
        t = thumb_bl_target(pc, h1, h2)
        if 0x08000000 <= t < 0x09000000:
            bl_targets.add(t)
    elif (h1 & 0xF800) == 0x4800:  # ldr rN, [pc, #imm]
        imm = (h1 & 0xFF) * 4
        pc_base = (pc + 4) & ~3
        tgt = pc_base + imm
        if 0x08000000 <= tgt <= 0x08FFFFFF:
            w = struct.unpack_from('<I', rom, tgt - 0x08000000)[0]
            if 0x08000000 <= w < 0x09000000:
                ldr_rom.add((tgt, w))

print("LaunchBattleAnimation 调的 bl 目标（ROM 8xxxxx）:")
for t in sorted(bl_targets):
    print(f"  0x{t:08X}")

print("\n引用的 ROM 数据字面量:")
for tgt, w in sorted(ldr_rom):
    print(f"  @0x{tgt:08X} = 0x{w:08X}")
