import struct
# 需要英文版 ROM 来反汇编英文版 LaunchBattleAnimation。
# 但我们只有日版 ROM。所以用日版偏移 0x08075738 - 0x2FC8 = 0x08072770 反汇编日版。
# 之前已经反汇编过日版 0x08072770 (LaunchBattleAnimation)。
# 关键：找它引用动画脚本数据的 ROM 地址（gBattleAnims 表）。

# 用 objdump 反汇编日版 LaunchBattleAnimation 完整，看所有 ldr 字面量
rom = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()

# 直接读日版 0x08072770 起的所有 ldr 字面量（pool 在函数末尾）
# 先看函数体长度，英文版 LaunchBattleAnimation 是 0x1b0 = 432 字节
# 日版 0x08072770 + 0x1b0 = 0x08072920
for addr in range(0x08072770, 0x08072920, 2):
    off = addr - 0x08000000
    h = struct.unpack_from('<H', rom, off)[0]
    # 找 ldr rX, [pc, #imm] 编码 E000: imm8*4
    if (h & 0xF800) == 0x4800:
        imm = (h & 0xFF) * 4
        pc_base = (addr + 4) & ~3
        tgt = pc_base + imm
        w = struct.unpack_from('<I', rom, tgt - 0x08000000)[0]
        print(f'  0x{addr:08X}: ldr r{(h>>8)&7}, [pc,#{(h&0xFF)*4}] @ {tgt:08X} = 0x{w:08X}')
