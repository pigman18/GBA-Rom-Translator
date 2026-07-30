#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5: Systematic scan for ALL pointer tables in FRLG/RS/Emerald JP ROMs.
Find runs of 4-byte valid GBA pointers, then decode pointed-to PCS strings."""
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
        elif 0x81<=b<=0x9F or 0xE0<=b<=0xEF:
            if i+1<len(raw) and 0x40<=raw[i+1]<=0xFC:
                try: out.append(bytes([b,raw[i+1]]).decode('shift_jis')); i+=2; continue
                except: pass
        i+=1
    return ''.join(out)

def is_valid_ptr(v, rom_size):
    return BASE <= v < BASE + rom_size

def scan_all_tables(rom_path, game_name, min_entries=15):
    rom = rom_path.read_bytes()
    rs = len(rom)
    results = []
    
    print(f"\n{'='*70}")
    print(f"SCANNING: {game_name}")
    print(f"{'='*70}")
    
    # Phase 1: Find all valid GBA pointers and their runs
    # We scan every 4 bytes looking for valid pointers
    ptr_locs = []  # (offset, target_offset)
    
    for off in range(0, rs - 3, 4):
        v = struct.unpack('<I', rom[off:off+4])[0]
        if is_valid_ptr(v, rs):
            ptr_locs.append((off, v - BASE))
    
    print(f"  Total valid 4-byte pointers: {len(ptr_locs)}")
    
    # Find dense runs of consecutive pointers
    # Group by contiguous blocks
    runs = []
    i = 0
    while i < len(ptr_locs):
        off = ptr_locs[i][0]
        run_start = off
        count = 1
        j = i + 1
        next_expected = run_start + 4
        
        while j < len(ptr_locs):
            if ptr_locs[j][0] == next_expected:
                count += 1
                next_expected += 4
                j += 1
            elif ptr_locs[j][0] < next_expected + 12:  # small gap
                # Check gap entries are also valid pointers
                gap_ok = True
                for g_off in range(next_expected, ptr_locs[j][0], 4):
                    gv = struct.unpack('<I', rom[g_off:g_off+4])[0]
                    if not is_valid_ptr(gv, rs):
                        gap_ok = False
                        break
                if gap_ok:
                    count += 1
                    next_expected = ptr_locs[j][0] + 4
                    j += 1
                else:
                    break
            else:
                break
        
        if count >= min_entries:
            run_end = run_start + count * 4
            runs.append((run_start, run_end, count))
        i = j
    
    print(f"  Dense pointer runs (>= {min_entries} consecutive): {len(runs)}")
    
    # Phase 2: For each run, decode pointed-to strings
    trainer_like = []
    for start, end, count in sorted(runs):
        # Collect all target offsets
        targets = []
        all_pcs = True
        valid_count = 0
        for k in range(count):
            off = start + k * 4
            v = struct.unpack('<I', rom[off:off+4])[0]
            if is_valid_ptr(v, rs):
                targets.append(v - BASE)
                valid_count += 1
        
        if valid_count < min_entries:
            continue
        
        # Decode first 3 and check if they look like PCS trainer names
        def looks_like_trainer_name(txt):
            if not txt: return False
            # Trainer names are typically 2-6 chars of katakana/hiragana, no control codes
            if len(txt) < 2 or len(txt) > 15: return False
            # Should start with katakana or hiragana
            return True
        
        # Get sample decoded strings
        samples = []
        for t in targets[:min(8, count)]:
            try:
                end_off = rom.find(b'\xff', t)
                if end_off != -1 and end_off - t <= 32:
                    txt = decode_pcs(rom[t:end_off+1])
                    samples.append(txt)
                else:
                    samples.append(f"[raw: {rom[t:t+8].hex()}]")
            except:
                samples.append("[decode err]")
        
        # Check if targets are in a reasonable range and close together
        if targets:
            t_min = min(targets)
            t_max = max(targets)
            span = t_max - t_min
        else:
            span = 0
        
        # Look for interesting patterns: mostly katakana names
        kata_count = sum(1 for s in samples if s and any('\u30A0' <= c <= '\u30FF' for c in s))
        
        if kata_count >= 3 or (samples and span < 0x2000):
            info = {
                "table": f"0x{start:X}..0x{end:X}",
                "entries": count,
                "target_range": f"0x{min(targets):X}..0x{max(targets):X}",
                "sample": samples[:8],
                "kata_count": kata_count,
            }
            
            # Print table info
            print(f"\n  Table: {info['table']} ({count} entries)")
            print(f"    Targets: {info['target_range']} (span=0x{max(targets)-min(targets):X})")
            for si, s in enumerate(samples):
                tidx = targets[si] if si < len(targets) else 0
                print(f"    [{si:3d}] 0x{tidx:X} = {s}")
            
            if count > 8:
                last_t = targets[-1]
                end_off = rom.find(b'\xff', last_t)
                last_txt = decode_pcs(rom[last_t:end_off+1]) if end_off != -1 and end_off - last_t <= 32 else "[?]"
                print(f"    [{count-1:3d}] 0x{last_t:X} = {last_txt}")
            
            trainer_like.append(info)
    
    return trainer_like

# ======== MAIN ========
rom_dir = Path("C:/code/GBA-Rom-Translator/roms/origin")

roms = [
    ("FireRed (BPRJ)", rom_dir / "POKEMON_FIRE_BPRJ00.gba"),
    ("LeafGreen (BPGJ)", rom_dir / "POKEMON_LEAF_BPGJ00.gba"),
    ("Ruby (AXVJ)", rom_dir / "POKEMON_RUBY_AXVJ00.gba"),
    ("Sapphire (AXPJ)", rom_dir / "POKEMON_SAPP_AXPJ00.gba"),
    ("Emerald (BPEJ)", rom_dir / "Pokemon Emerald Version(JP).gba"),
]

all_results = {}
for name, path in roms:
    if path.exists():
        tables = scan_all_tables(path, name, min_entries=15)
        all_results[name] = tables
    else:
        print(f"\n{name}: NOT FOUND at {path}")

# Summary
print("\n\n" + "="*70)
print("SUMMARY OF TRAINER NAME TABLE CANDIDATES")
print("="*70)
for name, tables in all_results.items():
    print(f"\n{name}: {len(tables)} candidate tables")
    for t in tables:
        print(f"  {t['table']}: {t['entries']} entries, targets={t['target_range']}, kata={t['kata_count']}/{len(t['sample'])}")
