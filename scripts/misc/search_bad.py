import struct
trans = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read()
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba','rb').read()

# 搜索坏值 0x04002DEA (LE EA 2D 00 04) 和 0x04002DE8 (LE E8 2D 00 04)
for val, label in ((0x04002DEA, '0x04002DEA'), (0x04002DE8, '0x04002DE8'), (0x08002DE8, '0x08002DE8'), (0x08002DEA, '0x08002DEA')):
    needle = struct.pack('<I', val)
    hits_t = []
    start = 0
    while True:
        j = trans.find(needle, start)
        if j < 0: break
        hits_t.append(j)
        start = j + 1
    hits_o = []
    start = 0
    while True:
        j = orig.find(needle, start)
        if j < 0: break
        hits_o.append(j)
        start = j + 1
    print(f'{label}: 成品 {len(hits_t)} 处, 原版 {len(hits_o)} 处')
    for h in hits_t[:10]:
        print(f'   成品 file 0x{h:06X} (mem 0x{0x08000000+h:08X})')
