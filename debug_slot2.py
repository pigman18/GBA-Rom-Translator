import struct

rom = open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba', 'rb').read()

slot_off = 0x09EA0000 - 0x08000000
table = rom[slot_off:slot_off+200000]

def fnv1a(data):
    h = 0x811C9DC5
    for b in data:
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h

target = fnv1a(bytes([0x19, 0x14, 0x07]))
print("Target hash for [19 14 07]: 0x%08X" % target)

i = 0
found = False
for n in range(7000):
    if i + 3 >= len(table):
        print("End of table at entry #%d" % n)
        break
    if table[i] == 0 and table[i+1] == 0 and table[i+2] == 0 and table[i+3] == 0:
        print("Sentinel at entry #%d offset %d" % (n, i))
        break
    eh = struct.unpack('<I', table[i:i+4])[0]
    if eh == target:
        ci = i + 4
        ch = []
        while ci < len(table) and table[ci] != 0xFF:
            ch.append(table[ci])
            ci += 1
        if ci < len(table):
            ch.append(0xFF)
        print("FOUND at entry #%d: hash=0x%08X chinese=%s" % (n, eh, bytes(ch).hex(' ')))
        found = True
        break
    ci = i + 4
    while ci < len(table) and table[ci] != 0xFF:
        ci += 1
    ci += 1
    i = ci

if not found:
    print("NOT found after %d entries! last_offset=%d" % (n, i))
