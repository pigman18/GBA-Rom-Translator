from pathlib import Path
import struct

rom = Path("roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()
needle = bytes([0xA2, 0xA1, 0xA6, 0xF9, 0x00])
hits = []
i = 0
while True:
    j = rom.find(needle, i)
    if j < 0:
        break
    hits.append(j)
    i = j + 1
print("body hits", len(hits), [hex(h) for h in hits[:8]])

off_base = 0x810000
tab_base = 0x820000
for h in hits[:5]:
    print(hex(h), rom[h : h + 32].hex())
    if h < tab_base:
        continue
    rel = h - tab_base
    codes = []
    for code in range(min(0x8000, (len(rom) - off_base) // 4)):
        o = struct.unpack_from("<I", rom, off_base + code * 4)[0]
        if o == rel:
            codes.append(code)
    print("  rel", hex(rel), "codes", [hex(c) for c in codes[:8]])

# width of first stream
if hits:
    stream = rom[hits[0] :]
    w = 0
    i = 0
    while stream[i] != 0xFF:
        c = stream[i]
        if c == 0xF9:
            if stream[i + 1] == 0:
                w += 12
                i += 4
            else:
                i += 4
            continue
        if c >= 0xFA:
            i += 1
            continue
        w += 8
        i += 1
    pad = 0x60 // 2 - w // 2
    print("width", w, "pad", pad, "left_tiles+", pad // 8, "cursor+", pad & 7)

# find slot F9 80 pointing at those codes
for code in range(min(0x8000, (len(rom) - off_base) // 4)):
    o = struct.unpack_from("<I", rom, off_base + code * 4)[0]
    if tab_base + o + 5 <= len(rom) and rom[tab_base + o : tab_base + o + 5] == needle:
        # search ROM for F9 80 hi lo (big-endian code in stream)
        hi, lo = (code >> 8) & 0xFF, code & 0xFF
        slot = bytes([0xF9, 0x80, hi, lo])
        # also little? engine might store hi lo as big
        locs = []
        k = 0
        while True:
            p = rom.find(slot, k)
            if p < 0 or p >= 0x800000:
                break
            locs.append(p)
            k = p + 1
            if len(locs) >= 5:
                break
        if locs:
            print("code", hex(code), "slots", [hex(x) for x in locs], "slotbytes", rom[locs[0] : locs[0] + 8].hex())
