#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v7: Targeted investigation of specific candidate string areas for trainer name tables."""
import struct
from pathlib import Path

BASE = 0x08000000

HIRAGANA = ("あいうえおかきくけこさしすせそたちつてと"
            "なにぬねのはひふへほまみむめもやゆよらりるれろ"
            "わをんぁぃぅぇぉゃゅょ"
            "がぎぐげござじずぜぞ"
            "だぢづでどばびぶべぼ"
            "ぱぴぷぺぽっ")
KATAKANA = ("アイウエオカキクケコサシスセソタチツテト"
            "ナニヌネノハヒフヘホマミムメモヤユヨラリルレロ"
            "ワヲンァィゥェォャュョ"
            "ガギグゲゴザジズゼゾ"
            "ダヂヅデドバビブベボ"
            "パピプペポッ")

def decode_pcs(raw):
    out,i=[],0
    while i<len(raw):
        b=raw[i]
        if b==0xFF: break
        if b in (0xFA,0xFB,0xFC,0xFD,0xFE): i+=1; continue
        if b in (0xF7,0xF8):
            if i+2<len(raw):
                try: out.append(bytes([raw[i+1],raw[i+2]]).decode('shift_jis')); i+=3; continue
                except: pass
            i+=1; continue
        if 0x01<=b<=0x50:
            idx=b-0x01
            out.append(HIRAGANA[idx] if idx<len(HIRAGANA) else f'[H{b:02X}]')
        elif 0x51<=b<=0xA0:
            idx=b-0x51
            out.append(KATAKANA[idx] if idx<len(KATAKANA) else f'[K{b:02X}]')
        elif 0xA1<=b<=0xAA: out.append(chr(ord('0')+b-0xA1))
        elif b==0xAB: out.append('!')
        elif b==0xAC: out.append('?')
        elif b==0xAD: out.append('.')
        elif b==0xB0: out.append('...')
        elif b==0x00: out.append(' ')
        elif 0xBB<=b<=0xD4: out.append(chr(ord('A')+b-0xBB))
        elif 0xD5<=b<=0xEE: out.append(chr(ord('a')+b-0xD5))
        i+=1
    return ''.join(out)

def get_pcs_string(rom, off):
    end = rom.find(b'\xff', off)
    if end == -1 or end - off > 128:
        return None
    return decode_pcs(rom[off:end+1])

def find_table_for_strings(rom, name, string_offsets, game_label):
    """Given a list of string offsets that are trainer names, find pointer tables."""
    print(f"\n{'='*70}")
    print(f"Targeted: {game_label}")
    
    rs = len(rom)
    
    # For each string offset, find all 4-byte pointer locations
    ptr_map = {}  # ptr_loc -> data_off
    for off in string_offsets:
        ptr_bytes = struct.pack('<I', BASE + off)
        pos = 0
        while pos < rs:
            pos = rom.find(ptr_bytes, pos)
            if pos == -1: break
            ptr_map[pos] = off
            pos += 4
    
    ptr_locs = sorted(ptr_map.keys())
    print(f"  String area: 0x{min(string_offsets):X}..0x{max(string_offsets):X} ({len(string_offsets)} strings)")
    print(f"  Found {len(ptr_locs)} pointer references to these strings")
    
    # Group into runs of consecutive 4-byte pointers
    runs = []
    i = 0
    while i < len(ptr_locs):
        start = ptr_locs[i]
        count = 1
        j = i + 1
        while j < len(ptr_locs):
            if ptr_locs[j] == ptr_locs[j-1] + 4:
                count += 1
                j += 1
            else:
                break
        if count >= 3:
            runs.append((start, count, [ptr_locs[k] for k in range(i, j)]))
        i = j
    
    if runs:
        print(f"  Found {len(runs)} pointer runs of 3+ consecutive:")
        for start, count, locs in sorted(runs):
            # Check targets
            target_info = []
            for l in locs:
                v = struct.unpack('<I', rom[l:l+4])[0]
                doff = v - BASE
                txt = get_pcs_string(rom, doff)
                target_info.append(f"0x{doff:X}={txt or '?'}")
            print(f"    0x{start:X}..0x{start+count*4:X}: {count} entries")
            for ti in target_info[:8]:
                print(f"      {ti}")
            if count > 8:
                print(f"      ... ({count} total)")
    else:
        print(f"  No consecutive pointer runs found (scattered references)")
        # Show the scattered pointers
        print(f"  Scattered ptr locations:")
        for pl in ptr_locs[:15]:
            v = struct.unpack('<I', rom[pl:pl+4])[0]
            doff = v - BASE
            txt = get_pcs_string(rom, doff)
            print(f"    0x{pl:X} -> 0x{doff:X} = {txt}")

# ======== MAIN ========
rom_dir = Path("C:/code/GBA-Rom-Translator/roms/origin")

# Emerald: candidate areas from v1/v2
# Area 1: 0x5CA9E8..0x5CAA0B  (ダイゴ, トウキ, ナギ, etc.)
emerald_candidates = [
    (rom_dir/"Pokemon Emerald Version(JP).gba", "Emerald Area1", range(0x5CA9E8, 0x5CAA10)),
    # Area 2: 0x5C8C44..0x5C8C6B  (アオギリ, マツブサ, etc.)
    (rom_dir/"Pokemon Emerald Version(JP).gba", "Emerald Area2", range(0x5C8C44, 0x5C8C70)),
]

for path, label, str_range in emerald_candidates:
    rom = path.read_bytes()
    # Find all valid PCS strings in the range
    offs = []
    pos = str_range.start
    while pos < str_range.stop:
        if rom[pos] == 0xFF:
            pos += 1
            continue
        txt = get_pcs_string(rom, pos)
        if txt and len(txt) >= 2:
            offs.append(pos)
            pos += len(txt.encode('shift_jis'))  # rough skip
        else:
            pos += 1
    print(f"\n  Strings found in {label} (0x{str_range.start:X}..0x{str_range.stop:X}):")
    for o in offs:
        txt = get_pcs_string(rom, o)
        print(f"    0x{o:X}: {txt}")
    
    # Now find pointer tables
    find_table_for_strings(rom, label, offs, label)

# Also check FRLG - the area around the location table for the trainer name table
# In English FRLG, trainer name table is right after some data following location table
# Location table is at 0x3B8834 (FR) with 109 entries

for fname, label in [
    ("POKEMON_FIRE_BPRJ00.gba", "FireRed after-loc-table"),
    ("POKEMON_LEAF_BPGJ00.gba", "LeafGreen after-loc-table"),
]:
    path = rom_dir / fname
    rom = path.read_bytes()
    
    # Location table: FireRed 0x3B8834, LeafGreen 0x3B86A4 (from v6)
    loc_table = 0x3B8834 if "FIRE" in fname else 0x3B86A4
    loc_end = loc_table + 109 * 4  # 109 entries
    print(f"\n{label}: location table ends at 0x{loc_end:X}")
    
    # Scan from loc_end to +0x2000 for 4-byte pointer tables
    # Look for any pointer table where targets are PCS strings
    # and specifically look for trainer names
    results = []
    for off in range(loc_end, min(loc_end + 0x2000, len(rom) - 3), 4):
        v = struct.unpack('<I', rom[off:off+4])[0]
        if not (BASE <= v < BASE + len(rom)):
            continue
        doff = v - BASE
        txt = get_pcs_string(rom, doff)
        if txt and len(txt) >= 2 and len(txt) <= 12:
            results.append((off, doff, txt))
    
    # Group into consecutive 4-byte runs
    if results:
        print(f"\n  Found {len(results)} valid string pointers in 0x{loc_end:X}..0x{loc_end+0x2000:X}")
        # Group by consecutive
        offs = [r[0] for r in results]
        runs = []
        i = 0
        while i < len(offs):
            start = offs[i]
            c = 1
            j = i + 1
            while j < len(offs) and offs[j] == offs[j-1] + 4:
                c += 1
                j += 1
            if c >= 5:
                runs.append((start, offs[j-1] + 4, c, i, j))
            i = j
        
        if runs:
            print(f"  Pointer runs with 5+ entries:")
            for start, end, c, si, ei in runs:
                print(f"    0x{start:X}..0x{end:X}: {c} entries")
                for k in range(min(8, c)):
                    idx = si + k
                    print(f"      [{k:3d}] {results[idx][2]}")
                if c > 8:
                    print(f"      [{c-1:3d}] {results[ei-1][2]}")
        else:
            # Show individual entries
            print(f"  Individual entries (no runs):")
            for off, doff, txt in results[:20]:
                print(f"    0x{off:X} -> 0x{doff:X}: {txt}")
