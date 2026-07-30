#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v6: Scan specific data regions for trainer name tables.
Only look at pointer tables where ALL targets are valid PCS strings."""
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
        else: pass
        i+=1
    return ''.join(out)

def is_valid_ptr(v, rom_size):
    return BASE <= v < BASE + rom_size

def find_ptr_tables_in_range(rom, search_start, search_end, stride=4, min_run=10):
    """Scan a region for pointer tables where targets are PCS strings."""
    rs = len(rom)
    results = []
    
    # Scan at stride intervals within range
    ptr_offsets = []  # [(offset, target)]
    for off in range(search_start, search_end - 3, stride):
        v = struct.unpack('<I', rom[off:off+4])[0]
        if is_valid_ptr(v, rs):
            ptr_offsets.append((off, v - BASE))
    
    # Group consecutive offsets
    i = 0
    while i < len(ptr_offsets):
        run = [(ptr_offsets[i][0], ptr_offsets[i][1])]
        j = i + 1
        while j < len(ptr_offsets):
            if ptr_offsets[j][0] == run[-1][0] + stride:
                run.append((ptr_offsets[j][0], ptr_offsets[j][1]))
                j += 1
            else:
                break
        if len(run) >= min_run:
            results.append(run)
        i = j
    
    return results

def validate_trainer_table(rom, ptr_run):
    """Check if a pointer run points to valid trainer names (PCS strings)."""
    rs = len(rom)
    decoded = []
    all_kata = True
    for poff, toff in ptr_run:
        if toff >= rs or toff < 0:
            decoded.append(None)
            all_kata = False
            continue
        end = rom.find(b'\xff', toff)
        if end == -1 or end - toff > 64 or end - toff < 1:
            decoded.append(None)
            all_kata = False
            continue
        try:
            txt = decode_pcs(rom[toff:end+1])
            decoded.append(txt)
            # Check if it looks like a trainer name (katakana/hiragana only, 2-12 chars)
            has_kata = any('\u30A0' <= c <= '\u30FF' or '\u3040' <= c <= '\u309F' for c in txt) if txt else False
            if not has_kata:
                all_kata = False
        except:
            decoded.append(None)
            all_kata = False
    
    return all_kata, decoded

def analyze_game(rom, game_name, data_region_start, data_region_end):
    print(f"\n{'='*70}")
    print(f"ANALYZING: {game_name}")
    rs = len(rom)
    
    # Find all 4-byte pointer runs in the data region
    temp_results = find_ptr_tables_in_range(rom, data_region_start, data_region_end, stride=4, min_run=20)
    print(f"  Found {len(temp_results)} pointer runs with >=20 entries in data region")
    
    # Validate each
    valid_tables = []
    for run in temp_results:
        valid, decoded = validate_trainer_table(rom, run)
        if valid:
            start = run[0][0]
            end = run[-1][0] + 4
            valid_tables.append((start, end, len(run), decoded[:10], run))
    
    if valid_tables:
        print(f"  {len(valid_tables)} look like trainer name tables!")
        for start, end, count, samples, run in valid_tables[:5]:
            targets = [t for _, t in run]
            print(f"\n  TABLE: 0x{start:X}..0x{end:X} ({count} entries)")
            print(f"    Targets: 0x{min(targets):X}..0x{max(targets):X}")
            for si, s in enumerate(samples[:8]):
                print(f"    [{si:3d}] 0x{run[si][1]:X} = {s}")
            if len(samples) >= count:
                pass
            else:
                print(f"    [{count-1:3d}] 0x{run[-1][1]:X} = {decode_pcs(rom[run[-1][1]:rom.find(b'\\xff',run[-1][1])+1]) if rom.find(b'\\xff',run[-1][1])!=-1 and rom.find(b'\\xff',run[-1][1])-run[-1][1]<=64 else '?'}")
    
    # Also check for 8-byte stride tables in data region
    temp_results_8 = find_ptr_tables_in_range(rom, data_region_start, data_region_end, stride=8, min_run=10)
    if temp_results_8:
        print(f"\n  Found {len(temp_results_8)} pointer runs with >=10 entries (stride=8)")
        for run in temp_results_8[:5]:
            valid, decoded = validate_trainer_table(rom, run)
            if valid:
                start = run[0][0]
                end = run[-1][0] + 8
                print(f"\n  8-STRIDE TABLE: 0x{start:X}..0x{end:X} ({len(run)} entries)")
                for si, s in enumerate(decoded[:5]):
                    if s: print(f"    [{si:3d}] 0x{run[si][1]:X} = {s}")
    
    # If no valid tables found using strict check, show approximate ones
    if not valid_tables:
        print(f"  No strictly valid trainer name tables found.")
        # Show tables with at least 50% katakana names
        for run in temp_results[:10]:
            valid, decoded = validate_trainer_table(rom, run)
            kata_ratio = sum(1 for d in decoded if d and any('\u30A0' <= c <= '\u30FF' or '\u3040' <= c <= '\u309F' for c in d)) / len(decoded)
            if kata_ratio > 0.3:
                start = run[0][0]
                end = run[-1][0] + 4
                print(f"  PARTIAL: 0x{start:X}..0x{end:X} ({len(run)} entries, {kata_ratio:.0%} kata)")
                for si, (s, (poff, toff)) in enumerate(zip(decoded[:6], run[:6])):
                    print(f"    [{si:3d}] 0x{toff:X} = {s or '?'}")


# ======== MAIN ========
rom_dir = Path("C:/code/GBA-Rom-Translator/roms/origin")

# For each ROM, define the "data region" to scan
# This is usually the upper half where pointer tables live
games = [
    # (name, path, search_start, search_end)
    ("FireRed", rom_dir/"POKEMON_FIRE_BPRJ00.gba", 0x180000, 0x1000000),
    ("LeafGreen", rom_dir/"POKEMON_LEAF_BPGJ00.gba", 0x180000, 0x1000000),
    ("Ruby", rom_dir/"POKEMON_RUBY_AXVJ00.gba", 0x300000, 0x800000),
    ("Sapphire", rom_dir/"POKEMON_SAPP_AXPJ00.gba", 0x300000, 0x800000),
    ("Emerald", rom_dir/"Pokemon Emerald Version(JP).gba", 0x500000, 0x1000000),
]

for name, path, ss, se in games:
    if path.exists():
        rom = path.read_bytes()
        # Also check specific known areas
        analyze_game(rom, name, ss, se)
