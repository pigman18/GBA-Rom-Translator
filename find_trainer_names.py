#!/usr/bin/env python3
"""Find trainer name pointer tables in all 5 Gen3 JP ROMs."""
import struct, sys
from pathlib import Path

BASE = 0x08000000

# ---- PCS Decoding ----
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
        if b == 0xFF:
            break
        if b in (0xFA, 0xFB, 0xFC, 0xFD, 0xFE):
            i += 1
            continue
        if b in (0xF7, 0xF8):
            if i + 2 < len(raw):
                try:
                    out.append(bytes([raw[i+1], raw[i+2]]).decode('shift_jis'))
                    i += 3
                    continue
                except UnicodeDecodeError:
                    pass
            i += 1
            continue
        if 0x01 <= b <= 0x50:
            idx = b - 0x01
            out.append(HIRAGANA[idx] if idx < len(HIRAGANA) else chr(0x3040 + b))
        elif 0x51 <= b <= 0xA0:
            idx = b - 0x51
            out.append(KATAKANA[idx] if idx < len(KATAKANA) else chr(0x30A0 + b))
        elif 0xA1 <= b <= 0xAA:
            out.append(chr(ord('0') + b - 0xA1))
        elif b == 0xAB:
            out.append('!')
        elif b == 0xAC:
            out.append('?')
        elif b == 0xAD:
            out.append('.')
        elif b == 0xAE:
            out.append('ー')
        elif b == 0xAF:
            out.append('·')
        elif b == 0xB0:
            out.append('…')
        elif b == 0xB1:
            out.append('「')
        elif b == 0xB2:
            out.append('」')
        elif b == 0xB3:
            out.append('『')
        elif b == 0xB4:
            out.append('』')
        elif b == 0xB5:
            out.append('♂')
        elif b == 0xB6:
            out.append('♀')
        elif b == 0xB7:
            out.append('¥')
        elif b == 0xB8:
            out.append(',')
        elif b == 0xB9:
            out.append('×')
        elif b == 0xBA:
            out.append('/')
        elif 0xBB <= b <= 0xD4:
            out.append(chr(ord('A') + b - 0xBB))
        elif 0xD5 <= b <= 0xEE:
            out.append(chr(ord('a') + b - 0xD5))
        elif b == 0x00:
            out.append(' ')
        elif 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF:
            if i + 1 < len(raw) and 0x40 <= raw[i+1] <= 0xFC:
                try:
                    out.append(bytes([b, raw[i+1]]).decode('shift_jis'))
                    i += 2
                    continue
                except:
                    pass
            out.append(f'[{b:02X}]')
        else:
            out.append(f'[{b:02X}]')
        i += 1
    return ''.join(out)

def encode_pcs_char(c):
    """Return PCS byte(s) for a single character, or None."""
    if c in HIRAGANA:
        idx = HIRAGANA.index(c)
        return bytes([0x01 + idx])
    if c in KATAKANA:
        idx = KATAKANA.index(c)
        return bytes([0x51 + idx])
    if '0' <= c <= '9':
        return bytes([0xA1 + ord(c) - ord('0')])
    if c == ' ':
        return bytes([0x00])
    if c == 'ー':
        return bytes([0xAE])
    if c == '·':
        return bytes([0xAF])
    try:
        sjis = c.encode('shift_jis')
        if len(sjis) == 2:
            return bytes([0xF7, sjis[0], sjis[1]])
        return None
    except:
        return None

def encode_pcs(s):
    out = bytearray()
    for c in s:
        b = encode_pcs_char(c)
        if b:
            out.extend(b)
        else:
            return None
    out.append(0xFF)
    return bytes(out)

# Known trainer names
KNOWN_NAMES = [
    "ダイゴ",   # Steven
    "ミツル",   # Wally
    "マツブサ", # Maxie
    "アオギリ", # Archie
    "ユウキ",   # Brendan
    "ハルカ",   # May
    "オダマキ", # Bir
    "シゲル",   # Gary/Shigeru (FRLG rival)
    "サカキ",   # Giovanni
    "カツラ",   # Blaine
    "ナツメ",   # Sabrina
    "エリカ",   # Erika
]

# Additional trainer names likely in each game
RSE_NAMES = KNOWN_NAMES  # All of the above
FRLG_NAMES = [
    "オーキド", # Oak
    "シゲル",   # Gary
    "サカキ",   # Giovanni
    "カツラ",   # Blaine
    "ナツメ",   # Sabrina
    "エリカ",   # Erika
    "カスミ",   # Misty
    "タケシ",   # Brock
    "マチス",   # Lt. Surge
    "アンズ",   # Koga (in Japanese: アンズ but it's キョウ... let me use the right names)
]

def try_pointer_table(rom, data_offsets, stride=4, max_gap=8, min_entries=10):
    """Try to find a pointer table pointing to given data offsets.
    
    For each data offset, look for the stored pointer (BASE + offset) as 4-byte LE.
    Then find runs of consecutive pointers.
    """
    if len(data_offsets) < min_entries:
        return []
    
    # For each data offset, find all pointer locations
    ptr_map = {}  # ptr_loc → [target_offset]
    for d_off in data_offsets:
        ptr_bytes = struct.pack('<I', BASE + d_off)
        pos = 0
        while True:
            pos = rom.find(ptr_bytes, pos)
            if pos == -1:
                break
            ptr_map.setdefault(pos, []).append(d_off)
            pos += 4
    
    # Find runs with stride spacing
    ptr_locs = sorted(ptr_map.keys())
    
    tables = []
    i = 0
    while i < len(ptr_locs):
        run_start = ptr_locs[i]
        run_locs = [run_start]
        j = i + 1
        while j < len(ptr_locs):
            gap = ptr_locs[j] - run_locs[-1]
            if gap % stride == 0 and gap <= max_gap * stride:
                # Check if gap is stride or near-strided
                expected = run_locs[-1] + stride
                if abs(ptr_locs[j] - expected) <= 2:
                    run_locs.append(ptr_locs[j])
                    j += 1
                else:
                    # Check if there's a valid pointer at the expected location
                    # (might be a gap in the table where entry points elsewhere)
                    break
            else:
                break
        if len(run_locs) >= min_entries:
            tables.append((run_start, run_locs[-1] + 4, len(run_locs), stride))
        i = j
    
    return tables

def search_rom(rom_path, game_name, search_names, search_region=None):
    """Search a ROM for trainer name data."""
    rom_data = rom_path.read_bytes()
    rom_size = len(rom_data)
    print(f"\n{'='*60}")
    print(f"{game_name}: {rom_path.name} ({rom_size} bytes)")
    print(f"{'='*60}")
    
    # Step 1: Find all occurrences of known trainer names
    found = {}  # name → [offsets]
    for name in search_names:
        pcs = encode_pcs(name)
        if pcs is None:
            print(f"  WARNING: Could not encode {name}")
            continue
        offsets = []
        pos = 0
        while True:
            pos = rom_data.find(pcs, pos)
            if pos == -1:
                break
            offsets.append(pos)
            pos += 1
        if offsets:
            found[name] = offsets
            sample = offsets[:5]
            print(f"  {name}: found at {', '.join(f'0x{o:X}' for o in sample)}{'...' if len(offsets) > 5 else ''} ({len(offsets)} total)")
    
    if not found:
        print("  No known names found!")
        return None
    
    # Step 2: For each name occurrence, check if there's a 4-byte LE pointer
    # pointing to it (BASE + offset)
    all_name_offsets = set()
    for offsets in found.values():
        all_name_offsets.update(offsets)
    
    # Search for pointer tables
    tables = try_pointer_table(rom_data, sorted(all_name_offsets), stride=4)
    
    print(f"\n  Candidate pointer tables (stride=4, min_entries=10):")
    for start, end, count, stride in sorted(tables):
        # Verify: check first few decoded entries
        sample_ptrs = []
        for k in range(min(5, count)):
            offset = start + k * stride
            ptr = struct.unpack('<I', rom_data[offset:offset+4])[0]
            data_off = ptr - BASE
            sample_ptrs.append(data_off)
        
        # Try to decode the strings
        decoded = []
        for d_off in sample_ptrs:
            end_pos = rom_data.find(b'\xff', d_off)
            if end_pos != -1 and end_pos - d_off < 256:
                decoded.append(decode_pcs(rom_data[d_off:end_pos+1]))
            else:
                decoded.append(f"[{d_off:X}]")
        
        print(f"    0x{start:X}..0x{end:X}: {count} entries (stride={stride})")
        print(f"      First: {'  |  '.join(f'{d:08X}={t}' for d, t in zip(sample_ptrs, decoded))}")
        
        # Check last entry too
        last_offset = start + (count - 1) * stride
        if count > 5:
            last_ptr = struct.unpack('<I', rom_data[last_offset:last_offset+4])[0]
            last_data_off = last_ptr - BASE
            end_pos = rom_data.find(b'\xff', last_data_off)
            if end_pos != -1 and end_pos - last_data_off < 256:
                last_decoded = decode_pcs(rom_data[last_data_off:end_pos+1])
            else:
                last_decoded = f"[{last_data_off:X}]"
            print(f"      Last ({count-1}): 0x{last_offset:X}=0x{last_ptr:08X}={last_decoded}")
    
    # Step 3: Also check if any names appear near location tables
    # For each occurrence, look at trail of names (check if there's a block of PCS strings)
    # Group nearby name occurrences
    sorted_offsets = sorted(all_name_offsets)
    clusters = []
    if sorted_offsets:
        cluster_start = sorted_offsets[0]
        prev = sorted_offsets[0]
        cluster_count = 1
        for off in sorted_offsets[1:]:
            if off - prev <= 4:
                # Same string, skip
                continue
            if off - prev < 32:
                cluster_count += 1
            else:
                if cluster_count >= 3:
                    clusters.append((cluster_start, prev, cluster_count))
                cluster_start = off
                cluster_count = 1
            prev = off
        if cluster_count >= 3:
            clusters.append((cluster_start, prev, cluster_count))
    
    if clusters:
        print(f"\n  String clusters (3+ nearby matches):")
        for start, end, count in clusters[:5]:
            # Decode all strings in this area
            strings = []
            pos = start
            while pos <= end + 32:
                if rom_data[pos] == 0xFF:
                    pos += 1
                    continue
                end_pos = rom_data.find(b'\xff', pos)
                if end_pos == -1 or end_pos - pos > 256:
                    pos += 1
                    continue
                if end_pos - pos >= 1:
                    decoded = decode_pcs(rom_data[pos:end_pos+1])
                    if decoded:
                        strings.append((pos, decoded))
                pos = end_pos + 1
                if len(strings) > 20:
                    break
            print(f"    0x{start:X}..0x{end:X} ({count} name hits, ~{len(strings)} strings)")
            for off, s in strings[:8]:
                print(f"      0x{off:X}: {s}")
    
    # Step 4: Check for non-4-byte stride tables (e.g., 8-byte strides)
    tables_8 = try_pointer_table(rom_data, sorted(all_name_offsets), stride=8, min_entries=5)
    if tables_8:
        print(f"\n  Candidate pointer tables (stride=8, min_entries=5):")
        for start, end, count, stride in sorted(tables_8):
            print(f"    0x{start:X}..0x{end:X}: {count} entries (stride={stride})")
    
    return {
        "found_names": found,
        "all_offsets": sorted(all_name_offsets),
        "tables_4": tables,
        "tables_8": tables_8,
        "clusters": clusters,
    }


# ========== Main ==========
rom_dir = Path("C:/code/GBA-Rom-Translator/roms/origin")
roms = {
    "Ruby (AXVJ)": rom_dir / "POKEMON_RUBY_AXVJ00.gba",
    "Sapphire (AXPJ)": rom_dir / "POKEMON_SAPP_AXPJ00.gba",
    "Emerald (BPEJ)": rom_dir / "Pokemon Emerald Version(JP).gba",
    "FireRed (BPRJ)": rom_dir / "POKEMON_FIRE_BPRJ00.gba",
    "LeafGreen (BPGJ)": rom_dir / "POKEMON_LEAF_BPGJ00.gba",
}

for name, path in roms.items():
    if not path.exists():
        print(f"WARNING: {name} not found at {path}")
        continue
    
    if "Ruby" in name or "Sapphire" in name or "Emerald" in name:
        names_to_search = RSE_NAMES
    else:
        names_to_search = FRLG_NAMES
    
    search_rom(path, name, names_to_search)
