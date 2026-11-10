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

print("=== InitTextPrinter @ 0x08002C68 (主) ===")
disasm(0x08002C68, 30)

print("\n=== 0x08002CFC（sub_802D798 调用的 InitTextPrinter 相关）===")
disasm(0x08002CFC, 30)
