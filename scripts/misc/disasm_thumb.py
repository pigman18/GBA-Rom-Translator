import struct

rom = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()

def disasm_thumb(rom, addr, count):
    out = []
    pc = addr & ~1
    for _ in range(count):
        a = pc - 0x08000000
        if a + 1 >= len(rom):
            break
        half = struct.unpack_from('<H', rom, a)[0]
        out.append((pc, half))
        pc += 2
    return out

# RunTextPrinter 0x08002DE8，反汇编 40 条半字
print("=== RunTextPrinter @ 0x08002DE8 ===")
for pc, h in disasm_thumb(rom, 0x08002DE8, 40):
    print(f'  0x{pc:08X}: {h:04X}')

# StringExpandPlaceholders 0x08004530
print("\n=== StringExpandPlaceholders @ 0x08004530 ===")
for pc, h in disasm_thumb(rom, 0x08004530, 40):
    print(f'  0x{pc:08X}: {h:04X}')
