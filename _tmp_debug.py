import struct
orig = open('roms/origin/POKEMON_RUBY_AXVJ00.gba', 'rb').read()
tran = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba', 'rb').read()

# call site 0x0808C1D6: ldr r4,[pc,#0x6c]; PC=0x0808C1D6+4=0x0808C1DA aligned=0x0808C1D8; +0x6C=0x0808C244
pool_addr = 0x0808C244
fo = pool_addr - 0x08000000
gpe_orig = struct.unpack_from('<I', orig, fo)[0]
gpe_tran = struct.unpack_from('<I', tran, fo)[0]
print('gPokedexEntries pool: orig=%08X tran=%08X' % (gpe_orig, gpe_tran))

# Beautifly = Hoenn dex? entry index in table. Just dump entry 10 name in both
for gpe, label in ((gpe_orig, 'ORIG'), (gpe_tran, 'TRAN')):
    off = gpe + 10*28 - 0x08000000
    b = orig[off:off+12] if label=='ORIG' else tran[off:off+12]
    print(label, 'entry10 name:', ' '.join('%02X' % x for x in b))
    # what immediately follows (to check terminator)
    e = gpe + 10*28
    print(label, '  name field len to 0x00:', )