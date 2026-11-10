import struct
rom = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()

def disasm(addr, count=20):
    pc = addr & ~1
    for i in range(count):
        a = pc - 0x08000000
        if a+1 >= len(rom): break
        h = struct.unpack_from('<H', rom, a)[0]
        print(f'  0x{pc:08X}: {h:04X}')
        pc += 2

print("=== 0x0802D7E0 - 0x0802D890（含 LR=0x0802D828/D868）===")
disasm(0x0802D7E0, 90)
