#!/usr/bin/env python3
"""v3: Investigate candidate areas in FRLG + RSE for trainer name tables."""
import struct
from pathlib import Path

BASE = 0x08000000

HIRAGANA = (
    "あいうえおかきくけこさしすせそたちつてと"
    "なにぬねのはひふへほまみむめもやゆよらりるれろ"
    "わをんぁぃぅぇぉゃゅょ"
    "がぎぐげござじずぜぞ"
    "だぢづでどばびぶべぼ"
    "ぱぴぷぺぽっ"
)
KATAKANA = (
    "アイウエオカキクケコサシスセソタチツテト"
    "ナニヌネノハヒフヘホマミムメモヤユヨラリルレロ"
    "ワヲンァィゥェォャュョ"
    "ガギグゲゴザジズゼゾ"
    "ダヂヅデドバビブベボ"
    "パピプペポッ"
)

def decode_pcs(raw):
    out = []
    i = 0
    while i < len(raw):
        b = raw[i]
        if b == 0xFF: break
        if b in (0xFA, 0xFB, 0xFC, 0xFD, 0xFE): i += 1; continue
        if b in (0xF7, 0xF8):
            if i + 2 < len(raw):
                try:
                    out.append(bytes([raw[i+1], raw[i+2]]).decode('shift_jis'))
                    i += 3; continue
                except: pass
            i += 1; continue
        if 0x01 <= b <= 0x50:
            idx = b - 0x01
            out.append(HIRAGANA[idx] if idx < len(HIRAGANA) else f'[H{b:02X}]')
        elif 0x51 <= b <= 0xA0:
            idx = b - 0x51
            out.append(KATAKANA[idx] if idx < len(KATAKANA) else f'[K{b:02X}]')
        elif 0xA1 <= b <= 0xAA: out.append(chr(ord('0') + b - 0xA1))
        elif b == 0xAB: out.append('!')
        elif b == 0xAC: out.append('?')
        elif b == 0xAD: out.append('.')
        elif b == 0xAE: out.append('-')
        elif b == 0xB0: out.append('...')
        elif b == 0x00: out.append(' ')
        elif 0xBB <= b <= 0xD4: out.append(chr(ord('A') + b - 0xBB))
        elif 0xD5 <= b <= 0xEE: out.append(chr(ord('a') + b - 0xD5))
        elif 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF:
            if i + 1 < len(raw) and 0x40 <= raw[i+1] <= 0xFC:
                try:
                    out.append(bytes([b, raw[i+1]]).decode('shift_jis'))
                    i += 2; continue
                except: pass
            out.append(f'[{b:02X}]')
        else: out.append(f'[{b:02X}]')
        i += 1
    return ''.join(out)

rom_dir = Path("C:/code/GBA-Rom-Translator/roms/origin")

# ========== FRLG: dump area around suspected trainer table ==========
print("="*70)
print("FRLG: Investigating area around 0x3B9394 and other candidate locations")
print("="*70)

for rom_name, path in [
    ("FireRed", rom_dir / "POKEMON_FIRE_BPRJ00.gba"),
    ("LeafGreen", rom_dir / "POKEMON_LEAF_BPGJ00.gba"),
]:
    rom = path.read_bytes()
    print(f"\n--- {rom_name} ---")
    
    # Check what's at 0x3B9394 (FireRed) / 0x3B9274 (LeafGreen)
    check_off = 0x3B9394 if "FIRE" in rom_name else 0x3B9274
    print(f"\nDump at 0x{check_off:X}..0x{check_off+0x40:X} (should-be pointer table):")
    for off in range(check_off, check_off + 0x40, 4):
        ptr = struct.unpack('<I', rom[off:off+4])[0]
        valid = "VALID" if BASE <= ptr < BASE + len(rom) else "invalid"
        data_off = ptr - BASE if BASE <= ptr < BASE + len(rom) else 0
        if valid == "VALID":
            txt = decode_pcs(rom[data_off:data_off+64])
        else:
            txt = ""
        print(f"  0x{off:X}: 0x{ptr:08X} ({valid}) -> {txt[:40]}")
    
    # Try reversing search: find trainer names in the GBATEK known range for FRLG
    # For FRLG Japanese, the trainer name table might be at a different offset.
    # Let me check around the location table area.
    # English FRLG: location table at 0x3B8834 (4-byte, 78 entries), trainer names at 0x3B9394
    
    # Let me search for known trainer name strings and find nearby pointer tables
    # Trainers: タケシ(Brock), カスミ(Misty), マチス(Lt.Surge), エリカ(Erika)
    # サカキ(Giovanni), カツラ(Blaine), ナツメ(Sabrina), シゲル(Gary)
    
    frlg_names = ["タケシ", "カスミ", "マチス", "エリカ", "サカキ", "カツラ", "ナツメ", "シゲル"]
    
    # Encode each
    encoded_names = {}
    for name in frlg_names:
        out = bytearray()
        for c in name:
            if c in KATAKANA:
                out.append(0x51 + KATAKANA.index(c))
            elif c in HIRAGANA:
                out.append(0x01 + HIRAGANA.index(c))
        out.append(0xFF)
        encoded_names[name] = bytes(out)
    
    print(f"\nSearching for FRLG trainer names in PCS encoding:")
    all_name_offsets = set()
    for name, pcs in encoded_names.items():
        offsets = []
        pos = 0
        while True:
            pos = rom.find(pcs, pos)
            if pos == -1: break
            offsets.append(pos)
            pos += 1
        if offsets:
            print(f"  {name}: {pcs.hex()} -> {len(offsets)} hits: {', '.join(f'0x{o:X}' for o in offsets[:5])}")
            all_name_offsets.update(offsets)
    
    # For each name offset, check if there's a pointer to it
    print(f"\nSearching for pointer references to these names:")
    ptr_map = {}  # data_off -> pointer locations
    for d_off in sorted(all_name_offsets):
        ptr_bytes = struct.pack('<I', BASE + d_off)
        locs = []
        pos = 0
        while True:
            pos = rom.find(ptr_bytes, pos)
            if pos == -1: break
            locs.append(pos)
            pos += 4
        if locs:
            ptr_map[d_off] = locs
            print(f"  0x{d_off:X}: pointers at {', '.join(f'0x{l:X}' for l in locs)}")
    
    # Find pointer tables (consecutive 4-byte pointers)
    all_ptr_locs = sorted(set(p for locs in ptr_map.values() for p in locs))
    
    # Find runs
    runs = []
    i = 0
    while i < len(all_ptr_locs):
        start = all_ptr_locs[i]
        count = 1
        j = i + 1
        while j < len(all_ptr_locs):
            expected = start + count * 4
            if all_ptr_locs[j] == expected:
                count += 1
                j += 1
            elif all_ptr_locs[j] < expected + 32:
                # Check gap entries
                gaps = (all_ptr_locs[j] - expected) // 4
                valid = True
                for g in range(gaps):
                    check = expected + g * 4
                    p = struct.unpack('<I', rom[check:check+4])[0]
                    if p < BASE or p >= BASE + len(rom):
                        valid = False
                        break
                if valid:
                    count += gaps + 1
                    j += 1
                else:
                    break
            else:
                break
        if count >= 10:
            runs.append((start, start + count * 4, count))
        i = j
    
    if runs:
        print(f"\nFound pointer tables (10+ entries):")
        for start, end, count in sorted(runs):
            # Decode first 5 and last 2
            samples = []
            for k in range(min(5, count)):
                ptr = struct.unpack('<I', rom[start + k*4:start + k*4 + 4])[0]
                txt = decode_pcs(rom[ptr-BASE:ptr-BASE+64])
                samples.append(f"[{k}]0x{ptr-BASE:X}={txt}")
            if count > 5:
                for k in [count-2, count-1]:
                    ptr = struct.unpack('<I', rom[start + k*4:start + k*4 + 4])[0]
                    txt = decode_pcs(rom[ptr-BASE:ptr-BASE+64])
                    samples.append(f"[{k}]0x{ptr-BASE:X}={txt}")
            print(f"  0x{start:X}..0x{end:X} ({count} entries):")
            for s in samples:
                print(f"    {s}")
    else:
        print(f"  No pointer tables found!")

# ========== RSE: Investigate the interesting clusters ==========
print("\n\n" + "="*70)
print("RSE: Investigating candidate trainer name data areas")
print("="*70)

for rom_name, path in [
    ("Ruby", rom_dir / "POKEMON_RUBY_AXVJ00.gba"),
    ("Sapphire", rom_dir / "POKEMON_SAPP_AXPJ00.gba"),
    ("Emerald", rom_dir / "Pokemon Emerald Version(JP).gba"),
]:
    rom = path.read_bytes()
    print(f"\n--- {rom_name} ---")
    
    # Investigate 0x3E9400 area (Ruby) / 0x3E941E area (Sapphire)
    # These contain the Archie and Maxie names - likely trainer CLASS names (class names)
    # Trainer class names include things like: たんパンこぞう, ミニスカート, etc.
    
    # Let me look at what's around 0x3E9400
    if "Ruby" in rom_name:
        check_area = 0x3E9400
    elif "Sapphire" in rom_name:
        check_area = 0x3E93F0
    else:
        check_area = 0x5C8C30  # Emerald area from v1 output
    
    print(f"\nDump strings around 0x{check_area:X}:")
    for off in range(check_area, min(check_area + 0x200, len(rom))):
        if rom[off] == 0xFF:
            continue
        # Check if this looks like a PCS string start (not in middle of pointer)
        # Decode and show
        end = rom.find(b'\xff', off)
        if end != -1 and end - off >= 1 and end - off <= 128:
            txt = decode_pcs(rom[off:end+1])
            if txt and len(txt) >= 2:
                print(f"  0x{off:X}: {txt}")
                off = end  # will skip past after loop increment
    
    # Also check the 0x1C8D78 area (script data with trainer names)
    # These ARE the actual trainer names used in battle scripts
    # (e.g., "ユウキ" appears in "ユウキと しょうぶ!" text)
    print(f"\nSpot-check script area 0x1C4xxx-0x1C9xxx for trainer names:")
    # Look for pointer tables that might reference these names
    
    # For Ruby, check area around location table (0x3BEF70)
    print(f"\nDump around location table (0x3BEF70 for RS, 0x57CD70 for Emerald):")
    if "Emerald" in rom_name:
        loc_table = 0x57CD70
        n_locs = 101
        stride = 8
    else:
        loc_table = 0x3BEF70
        n_locs = 88
        stride = 8
    
    # Dump a few entries of location table
    for i in range(min(5, n_locs)):
        off = loc_table + i * stride
        ptr = struct.unpack('<I', rom[off:off+4])[0]
        data_off = ptr - BASE
        txt = decode_pcs(rom[data_off:data_off+64])
        print(f"  Loc[{i}] at 0x{off:X}: ptr=0x{ptr:08X} off=0x{data_off:X} = {txt}")
    
    # After the location table, check what's there
    loc_end = loc_table + n_locs * stride
    print(f"\nLocation table ends at 0x{loc_end:X}")
    print(f"Dump 0x100 bytes after location table:")
    for off in range(loc_end, min(loc_end + 0x100, len(rom)), 4):
        val = struct.unpack('<I', rom[off:off+4])[0]
        valid = "PTR" if BASE <= val < BASE + len(rom) else "val"
        extra = ""
        if valid == "PTR":
            extra = decode_pcs(rom[val-BASE:val-BASE+48])
        if val != 0:
            print(f"  0x{off:X}: 0x{val:08X} ({valid}) {extra}")
