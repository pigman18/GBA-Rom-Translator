import struct
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()
trans = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()
for addr in (0x080415A0, 0x08042408, 0x08042B14, 0x08041760, 0x08042620, 0x08042C38):
    off = addr - 0x08000000
    print(f'{addr:08X}:')
    ow = [hex(struct.unpack_from('<I', orig, off+i)[0]) for i in range(0,16,4)]
    tw = [hex(struct.unpack_from('<I', trans, off+i)[0]) for i in range(0,16,4)]
    print('  origin:', ' '.join(ow))
    print('  trans :', ' '.join(tw))
    print('  origin bytes:', orig[off:off+16].hex(' '))
    print('  trans  bytes:', trans[off:off+16].hex(' '))
    print()
