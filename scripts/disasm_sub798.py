import struct
rom = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()

def disasm(addr, count):
    pc = addr & ~1
    for i in range(count):
        a = pc - 0x08000000
        if a+1 >= len(rom): break
        h = struct.unpack_from('<H', rom, a)[0]
        print(f'  0x{pc:08X}: {h:04X}')
        pc += 2

# sub_802D798 完整入口 0x0802D798 到 0x0802D86E
print("=== sub_802D798 完整 (0x0802D798 - 0x0802D870) ===")
disasm(0x0802D798, 110)
