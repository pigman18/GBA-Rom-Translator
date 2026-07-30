#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v10: Full characterization of trainer data structures in all 5 JP ROMs."""
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

def identify_trainer_data(rom, name, search_start, search_end, stride=0x20, min_entries=5):
    """Scan for trainer data structures with inline PCS names at fixed stride."""
    rs = len(rom)
    results = []
    
    off = search_start
    while off + stride <= search_end:
        # Check if this 32-byte block looks like a trainer entry
        # Look for a PCS string in the last 16 bytes
        block = rom[off:off+stride]
        
        # Find the PCS terminator in the last half of the block
        for name_start in range(stride//2, stride-2):
            if block[name_start] == 0xFF:
                continue
            # Check for FF terminator a few bytes later
            end = block.find(b'\xff', name_start)
            if end != -1 and 2 <= end - name_start <= 10:  # name length 2-10 chars
                # Good candidate! Decode
                txt = decode_pcs(block[name_start:end+1])
                if txt and len(txt) >= 2:
                    # Check there's no PCS data before the name start (in the header area)
                    has_pcs_before = False
                    for check_off in range(0, name_start - 2):
                        if block[check_off] >= 0x01 and block[check_off] <= 0xEE:
                            pass  # Could be PCS data before name - that's OK for the header
                    
                    results.append((off, txt, name_start))
                    off += stride
                    break
        else:
            off += 1  # Skip 1 byte if no match
    
    return results

def find_table_boundaries(rom, known_offsets, stride=0x20):
    """Given known offsets within the table, find start and end."""
    # The table starts at the first offset that has a valid entry going backward
    # We know the stride, so just find the first entry
    if not known_offsets:
        return None, None
    
    earliest = min(known_offsets)
    
    # Walk backward by stride to find the start
    while earliest >= stride:
        cand = earliest - stride
        # Check if candidate has valid structure
        end = rom.find(b'\xff', cand + stride - 16)  # look in last 16 bytes
        if end == -1 or end - (cand + stride - 16) > 12:
            # Also check if there's a name somewhere in the last half
            found_name = False
            for pos in range(cand + stride//2, cand + stride - 2):
                if rom[pos] == 0xFF: continue
                e = rom.find(b'\xff', pos)
                if e != -1 and 2 <= e - pos <= 10:
                    txt = decode_pcs(rom[pos:e+1])
                    if txt and len(txt) >= 2:
                        found_name = True
                        break
            if not found_name:
                break
        earliest = cand
    
    latest = max(known_offsets)
    while latest + stride < len(rom):
        cand = latest + stride
        found_name = False
        for pos in range(cand + stride//2, cand + stride - 2):
            if rom[pos] == 0xFF: continue
            e = rom.find(b'\xff', pos)
            if e != -1 and 2 <= e - pos <= 10:
                txt = decode_pcs(rom[pos:e+1])
                if txt and len(txt) >= 2:
                    found_name = True
                    break
        if not found_name:
            break
        latest = cand
    
    return earliest, latest + stride

# ======== MAIN ========
rom_dir = Path("C:/code/GBA-Rom-Translator/roms/origin")

games = [
    ("FireRed",    rom_dir/"POKEMON_FIRE_BPRJ00.gba",    0x201300, 0x202C00),
    ("LeafGreen",  rom_dir/"POKEMON_LEAF_BPGJ00.gba",    0x201300, 0x202C00),
    ("Ruby",       rom_dir/"POKEMON_RUBY_AXVJ00.gba",    0x1C4000, 0x1CA000),
    ("Sapphire",   rom_dir/"POKEMON_SAPP_AXPJ00.gba",    0x1C4000, 0x1CA000),
    ("Emerald",    rom_dir/"Pokemon Emerald Version(JP).gba", 0x2E3000, 0x2EA000),
]

for name, path, ss, se in games:
    if not path.exists():
        print(f"\n{name}: NOT FOUND")
        continue
    
    rom = path.read_bytes()
    print(f"\n{'='*70}")
    print(f"{name}: Scanning for trainer data structures")
    
    results = identify_trainer_data(rom, name, ss, se, stride=0x20, min_entries=3)
    
    if results:
        print(f"  Found {len(results)} candidate entries in range")
        
        # Find boundaries
        known_offsets = [r[0] for r in results]
        table_start, table_end = find_table_boundaries(rom, known_offsets, stride=0x20)
        
        if table_start:
            print(f"  TABLE BOUNDARIES: 0x{table_start:X}..0x{table_end:X} ({table_end-table_start} bytes, {(table_end-table_start)//0x20} entries)")
        
        # Show entries
        for off, txt, name_start in results[:30]:
            print(f"    0x{off:X}: name at +0x{name_start:X} = {txt}")
        
        if len(results) > 30:
            print(f"    ... ({len(results)} total)")
        
        # Show last 5
        for off, txt, name_start in results[-5:]:
            print(f"    0x{off:X}: name at +0x{name_start:X} = {txt}")
    else:
        print(f"  No candidate entries found")

# Also check FRLG more carefully - check beyond 0x202C00
print("\n" + "="*70)
print("FireRed: Extended scan to 0x204000")
rom = (rom_dir/"POKEMON_FIRE_BPRJ00.gba").read_bytes()
results = identify_trainer_data(rom, "FireRed-ext", 0x202C00, 0x204000, stride=0x20, min_entries=3)
if results:
    print(f"  Found {len(results)} entries in extended range")
    for off, txt, ns in results[:15]:
        print(f"    0x{off:X}: {txt}")
