#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8: Dump raw hex around interesting areas and decode properly."""
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

def dump_hex_pcs(rom, off, length=64):
    """Dump hex bytes and PCS decode from offset."""
    data = rom[off:off+length]
    hex_str = data.hex()
    # Find all FF-terminated strings
    strings = []
    pos = 0
    while pos < len(data):
        if data[pos] == 0xFF:
            strings.append(f"  ")
            pos += 1
            continue
        end = data.find(b'\xff', pos)
        if end == -1 or end - pos > 64:
            break
        txt = decode_pcs(data[pos:end+1])
        strings.append((pos, end-pos+1, txt))
        pos = end + 1
        if len(strings) > 15:
            break
    
    # Print hex with markers for string boundaries
    # Group into lines of 16 bytes
    result = []
    for row in range(0, len(data), 16):
        row_data = data[row:row+16]
        hex_part = ' '.join(f'{b:02X}' for b in row_data)
        addr = off + row
        result.append(f"  0x{addr:06X}: {hex_part}")
    
    for s in strings:
        if isinstance(s, tuple):
            pos, length, txt = s
            result.append(f"    STR at +0x{pos:02X} (len {length}): {txt}")
    
    return '\n'.join(result)

rom_dir = Path("C:/code/GBA-Rom-Translator/roms/origin")

print("="*70)
print("EMERALD: Dump at 0x5CA9E8 (trainer name candidate)")
print("="*70)
rom = (rom_dir/"Pokemon Emerald Version(JP).gba").read_bytes()
print(dump_hex_pcs(rom, 0x5CA9E8, 64))

print("\n" + "="*70)
print("EMERALD: Dump at 0x5C8C44 (special character/champion names)")
print("="*70)
print(dump_hex_pcs(rom, 0x5C8C44, 64))

# Now let's check FRLG - look at what's at known English offsets in the Japanese ROM
print("\n" + "="*70)
print("FIRE RED: Dump at 0x3B8834 (location table)")
print("="*70)
rom_fr = (rom_dir/"POKEMON_FIRE_BPRJ00.gba").read_bytes()
# Show first 10 entries
for i in range(10):
    off = 0x3B8834 + i * 4
    v = struct.unpack('<I', rom_fr[off:off+4])[0]
    if BASE <= v < BASE + len(rom_fr):
        doff = v - BASE
        txt = decode_pcs(rom_fr[doff:doff+64])
        print(f"  0x{off:X}: 0x{v:08X} -> 0x{doff:X} = {txt}")

print(f"\nLocation table ends at 0x{0x3B8834+109*4:X}")
print(f"Next 0x200 bytes:")
print(dump_hex_pcs(rom_fr, 0x3B89E8, 0x200))

# Check 0x3B9394 (English trainer table location)
print("\n" + "="*70)
print("FIRE RED: Dump at 0x3B9394 (expected trainer name table)")
print("="*70)
for i in range(20):
    off = 0x3B9394 + i * 4
    v = struct.unpack('<I', rom_fr[off:off+4])[0]
    valid = "PTR" if BASE <= v < BASE + len(rom_fr) else "val"
    extra = ""
    if valid == "PTR":
        txt = decode_pcs(rom_fr[v-BASE:v-BASE+64])
        extra = f" -> {txt}"
    print(f"  0x{off:X}: 0x{v:08X} ({valid}){extra}")

# Search 0x3B89E8 onward for ANY 4-byte pointer table
print("\n" + "="*70)
print("FIRE RED: Scan 0x3BA000..0x3BD000 for sequential 4-byte pointer tables")
print("="*70)
scan_start = 0x3BA000
scan_end = 0x3BD000
ptr_runs = []
cur_run = None
for off in range(scan_start, scan_end, 4):
    v = struct.unpack('<I', rom_fr[off:off+4])[0]
    if BASE <= v < BASE + len(rom_fr):
        if cur_run is None:
            cur_run = [off]
        elif off == cur_run[-1] + 4:
            cur_run.append(off)
        else:
            if len(cur_run) >= 30:
                ptr_runs.append((cur_run[0], cur_run[-1]+4, len(cur_run)))
            cur_run = [off]
    else:
        if cur_run is not None and len(cur_run) >= 30:
            ptr_runs.append((cur_run[0], cur_run[-1]+4, len(cur_run)))
        cur_run = None

if cur_run and len(cur_run) >= 30:
    ptr_runs.append((cur_run[0], cur_run[-1]+4, len(cur_run)))

print(f"Found {len(ptr_runs)} runs of 30+ valid pointers:")
for start, end, count in sorted(ptr_runs):
    # Decode first 3
    samples = []
    for k in range(min(3, count)):
        v = struct.unpack('<I', rom_fr[start+k*4:start+k*4+4])[0]
        txt = decode_pcs(rom_fr[v-BASE:v-BASE+64]) if BASE <= v < BASE + len(rom_fr) else "?"
        samples.append(f"0x{v-BASE:X}={txt}")
    # Last
    v = struct.unpack('<I', rom_fr[end-4:end])[0]
    last_txt = decode_pcs(rom_fr[v-BASE:v-BASE+64]) if BASE <= v < BASE + len(rom_fr) else "?"
    print(f"  0x{start:X}..0x{end:X} ({count} entries): {samples[0]} ... {last_txt}")
