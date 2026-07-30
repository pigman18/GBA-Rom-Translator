#!/usr/bin/env python3
"""Find trainer name pointer tables in all 5 Gen3 JP ROMs. v2"""
import struct, sys
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
            out.append(HIRAGANA[idx] if idx < len(HIRAGANA) else f'[H{b:02X}]')
        elif 0x51 <= b <= 0xA0:
            idx = b - 0x51
            out.append(KATAKANA[idx] if idx < len(KATAKANA) else f'[K{b:02X}]')
        elif 0xA1 <= b <= 0xAA:
            out.append(chr(ord('0') + b - 0xA1))
        elif b == 0xAB:
            out.append('!')
        elif b == 0xAC:
            out.append('?')
        elif b == 0xAD:
            out.append('.')
        elif b == 0xAE:
            out.append('-')
        elif b == 0xB0:
            out.append('...')
        elif b == 0x00:
            out.append(' ')
        elif 0xBB <= b <= 0xD4:
            out.append(chr(ord('A') + b - 0xBB))
        elif 0xD5 <= b <= 0xEE:
            out.append(chr(ord('a') + b - 0xD5))
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

def encode_to_pcs(s):
    """Encode a katakana string to PCS bytes."""
    out = bytearray()
    for c in s:
        if c in KATAKANA:
            idx = KATAKANA.index(c)
            out.append(0x51 + idx)
        elif c in HIRAGANA:
            idx = HIRAGANA.index(c)
            out.append(0x01 + idx)
        else:
            try:
                sjis = c.encode('shift_jis')
                if len(sjis) == 2:
                    out.extend([0xF7, sjis[0], sjis[1]])
                else:
                    return None
            except:
                return None
    out.append(0xFF)
    return bytes(out)

def hexdump_pcs(rom, offset, max_len=64):
    """Return hex bytes up to FF terminator."""
    end = rom.find(b'\xff', offset)
    if end == -1 or end - offset > max_len:
        end = offset + max_len
    return rom[offset:end+1].hex()

# ======== FRLG KNOWN TABLES ========
def verify_frlg(rom, name):
    """Verify FireRed (0x3B9394) or LeafGreen (0x3B9274) trainer name table."""
    if "FIRE" in name:
        table_off = 0x3B9394
    elif "LEAF" in name:
        table_off = 0x3B9274
    else:
        return
    
    print(f"\n--- {name}: verifying known table at 0x{table_off:X} ---")
    n = 362
    # Read pointer table
    ptrs = []
    for i in range(n):
        off = table_off + i * 4
        ptr = struct.unpack('<I', rom[off:off+4])[0]
        data_off = ptr - BASE
        ptrs.append((off, ptr, data_off))
    
    # Find string data range
    data_offsets = sorted(set(p[2] for p in ptrs))
    min_data = min(data_offsets)
    max_data = max(data_offsets)
    
    # Find string end (last FF terminator)
    last_end = max_data
    for d_off in data_offsets:
        end = rom.find(b'\xff', d_off)
        if end != -1 and end > last_end:
            last_end = end
    
    print(f"  Entry count: {n}")
    print(f"  Table: 0x{table_off:X}..0x{table_off + n*4:X} ({(n*4)} bytes)")
    print(f"  Strings: 0x{min_data:X}..0x{last_end+1:X}")
    
    # Decode first 10 and last 3
    print(f"  First 10 entries:")
    for i in range(min(10, n)):
        d_off = ptrs[i][2]
        decoded = decode_pcs(rom[d_off:d_off+128])
        print(f"    [{i:3d}] ptr=0x{ptrs[i][1]:08X} off=0x{d_off:X} = {decoded}")
    
    print(f"  Last 3 entries:")
    for i in range(n-3, n):
        d_off = ptrs[i][2]
        decoded = decode_pcs(rom[d_off:d_off+128])
        print(f"    [{i:3d}] ptr=0x{ptrs[i][1]:08X} off=0x{d_off:X} = {decoded}")
    
    return min_data, last_end + 1

# ======== RSE SEARCH ========
def find_string_block(rom, search_bytes, near_offsets=None):
    """Find all occurrences and return them sorted."""
    results = []
    pos = 0
    while True:
        pos = rom.find(search_bytes, pos)
        if pos == -1:
            break
        if near_offsets is None:
            results.append(pos)
        else:
            for near in near_offsets:
                if abs(pos - near) < 0x10000:
                    results.append(pos)
                    break
        pos += 1
    return sorted(set(results))

def search_rse(rom, name):
    """Search RSE for trainer name pointer tables."""
    print(f"\n{'='*60}")
    print(f"=== {name} ===")
    print(f"{'='*60}")
    
    # Known RSE trainer names in PCS bytes
    rse_names = {
        "Daigo": "ダイゴ",
        "Mitsuru": "ミツル", 
        "Maxie": "マツブサ",
        "Archie": "アオギリ",
        "Yuki": "ユウキ",
        "Haruka": "ハルカ",
    }
    
    # Encode each
    encoded = {}
    for key, jp in rse_names.items():
        pcs = encode_to_pcs(jp)
        if pcs:
            encoded[key] = pcs
            print(f"  {jp} ({key}): {pcs.hex()}")
    
    # Find all occurrences
    print(f"\n  Searching for known trainer names...")
    all_offsets = []
    for key, pcs in encoded.items():
        offsets = find_string_block(rom, pcs)
        if offsets:
            print(f"    {key}: {len(offsets)} hits -> {', '.join(f'0x{o:X}' for o in offsets[:5])}")
            all_offsets.extend(offsets)
    
    if not all_offsets:
        print("  No names found!")
        return
    
    # Find which occurrences have 4-byte pointers pointing TO them
    print(f"\n  Looking for pointer tables...")
    
    # For each offset, create the GBA pointer and search for it
    ptr_targets = {}  # data_offset -> [ptr_locations]
    for d_off in all_offsets:
        ptr_bytes = struct.pack('<I', BASE + d_off)
        pos = 0
        locs = []
        while True:
            pos = rom.find(ptr_bytes, pos)
            if pos == -1:
                break
            locs.append(pos)
            pos += 4
        if locs:
            ptr_targets[d_off] = locs
    
    if not ptr_targets:
        print("  No pointer references found!")
        return
    
    # Now look for tables: find runs of consecutive 4-byte pointers
    # Collect all pointer locations
    all_ptr_locs = set()
    for locs in ptr_targets.values():
        all_ptr_locs.update(locs)
    all_ptr_locs = sorted(all_ptr_locs)
    
    # For each candidate table start, check if it's a valid table
    # by seeing if it points to a contiguous block of strings
    print(f"\n  Searched {len(all_ptr_locs)} pointer locations, looking for tables...")
    
    # Strategy: For each group of nearby data offsets that look like names,
    # check if there's a pointer table somewhere
    
    # Group data offsets that are close together
    sorted_data = sorted(set(all_offsets))
    clusters = []
    i = 0
    while i < len(sorted_data):
        start = sorted_data[i]
        j = i + 1
        while j < len(sorted_data) and sorted_data[j] - sorted_data[j-1] <= 64:
            j += 1
        cluster = sorted_data[i:j]
        if len(cluster) >= 5:
            clusters.append(cluster)
        i = j
    
    print(f"  Found {len(clusters)} data clusters with 5+ name hits:")
    for ci, cluster in enumerate(clusters):
        print(f"    Cluster {ci}: {len(cluster)} offsets, range 0x{cluster[0]:X}..0x{cluster[-1]:X}")
        
        # Check for 4-byte pointer tables pointing to these
        d_set = set(cluster)
        ptr_counts = {}  # ptr_offset -> count of targets matched
        for d_off in d_set:
            if d_off in ptr_targets:
                for ploc in ptr_targets[d_off]:
                    ptr_counts[ploc] = ptr_counts.get(ploc, 0) + 1
        
        # Find runs of consecutive 4-byte pointers
        ptr_locs_sorted = sorted(ptr_counts.keys())
        
        # Find continuous runs
        run_starts = []
        i2 = 0
        while i2 < len(ptr_locs_sorted):
            run_start = ptr_locs_sorted[i2]
            run_len = 1
            i3 = i2 + 1
            while i3 < len(ptr_locs_sorted):
                expected = run_start + run_len * 4
                if ptr_locs_sorted[i3] == expected:
                    run_len += 1
                    i3 += 1
                elif ptr_locs_sorted[i3] < run_start + run_len * 4 + 8:
                    # Small gap - might still be the same table
                    gap_entries = (ptr_locs_sorted[i3] - expected) // 4
                    # Check if gap entries are also valid pointers
                    all_valid = True
                    for g in range(1, gap_entries + 1):
                        gap_ptr_off = expected + (g - 1) * 4
                        gap_ptr = struct.unpack('<I', rom[gap_ptr_off:gap_ptr_off+4])[0]
                        if gap_ptr < BASE or gap_ptr >= BASE + len(rom):
                            all_valid = False
                            break
                    if all_valid:
                        run_len += gap_entries + 1
                        i3 += 1
                    else:
                        break
                else:
                    break
            if run_len >= 5:
                run_starts.append((run_start, run_len, run_start + run_len * 4))
            i2 = i3
        
        if run_starts:
            print(f"    Potential pointer tables ({len(run_starts)} candidates):")
            for rs_start, rs_len, rs_end in run_starts[:10]:
                # Decode first few
                sample = []
                for k in range(min(5, rs_len)):
                    po = rs_start + k * 4
                    ptr = struct.unpack('<I', rom[po:po+4])[0]
                    doff = ptr - BASE
                    txt = decode_pcs(rom[doff:doff+128])
                    sample.append(f"0x{doff:X}={txt}")
                last_doff = struct.unpack('<I', rom[rs_end-4:rs_end])[0] - BASE
                last_txt = decode_pcs(rom[last_doff:last_doff+128])
                print(f"      0x{rs_start:X}..0x{rs_end:X} ({rs_len} entries):")
                print(f"        First:  {' | '.join(sample)}")
                print(f"        Last:   [{rs_len-1}] 0x{last_doff:X}={last_txt}")
    
    return clusters

# ======== MAIN ========
rom_dir = Path("C:/code/GBA-Rom-Translator/roms/origin")

roms = {
    "FIRE_BPRJ00": rom_dir / "POKEMON_FIRE_BPRJ00.gba",
    "LEAF_BPGJ00": rom_dir / "POKEMON_LEAF_BPGJ00.gba",
    "RUBY_AXVJ00": rom_dir / "POKEMON_RUBY_AXVJ00.gba",
    "SAPP_AXPJ00": rom_dir / "POKEMON_SAPP_AXPJ00.gba",
    "EMERALD_BPEJ": rom_dir / "Pokemon Emerald Version(JP).gba",
}

# 1. FRLG verification
for name in ["FIRE_BPRJ00", "LEAF_BPGJ00"]:
    path = roms[name]
    if path.exists():
        rom = path.read_bytes()
        verify_frlg(rom, name)

# 2. RSE search
for name in ["RUBY_AXVJ00", "SAPP_AXPJ00", "EMERALD_BPEJ"]:
    path = roms[name]
    if path.exists():
        rom = path.read_bytes()
        search_rse(rom, name)
    else:
        print(f"{name}: NOT FOUND at {path}")
