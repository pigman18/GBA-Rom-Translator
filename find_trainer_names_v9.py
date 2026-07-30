#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v9: Deep dive into FRLG and RSE trainer data structures."""
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

def find_pcs_strings(rom, start, end):
    """Find all PCS strings in a range."""
    strings = []
    pos = start
    while pos < end:
        if rom[pos] in (0xFF, 0x00) or rom[pos] in (0xFA,0xFB,0xFC,0xFD,0xFE):
            pos += 1
            continue
        # Check if it looks like a PCS string start (first byte should be hiragana/katakana)
        b = rom[pos]
        if (0x01 <= b <= 0xA0) or (0xBB <= b <= 0xEE):
            e = rom.find(b'\xff', pos)
            if e != -1 and 1 <= e - pos <= 32:
                txt = decode_pcs(rom[pos:e+1])
                if txt and len(txt) >= 1:
                    strings.append((pos, txt))
                    pos = e + 1
                    continue
        pos += 1
    return strings

def hexdump(rom, off, length):
    """Simple hex dump."""
    lines = []
    for row in range(0, length, 16):
        row_data = rom[off+row:off+row+16]
        hex_part = ' '.join(f'{b:02X}' for b in row_data)
        ascii_part = ''.join(chr(b) if 0x20 <= b <= 0x7E else '.' for b in row_data)
        lines.append(f"  0x{off+row:06X}: {hex_part}  {ascii_part}")
    return '\n'.join(lines)

rom_dir = Path("C:/code/GBA-Rom-Translator/roms/origin")

print("="*70)
print("FIRE RED: Hex dump of 0x19CB00..0x19CD00 (trainer name cluster)")
print("="*70)
rom = (rom_dir/"POKEMON_FIRE_BPRJ00.gba").read_bytes()
print(hexdump(rom, 0x19CB00, 0x200))

# Also check around 0x201380 (another cluster)
print("\n" + "="*70)
print("FIRE RED: Hex dump of 0x201300..0x201500")
print("="*70)
print(hexdump(rom, 0x201300, 0x200))

# Now for RSE: check 0x3E9400 area (Ruby)
print("\n" + "="*70)
print("RUBY: Hex dump of 0x3E9400..0x3E9600")
print("="*70)
rom_ru = (rom_dir/"POKEMON_RUBY_AXVJ00.gba").read_bytes()
print(hexdump(rom_ru, 0x3E9400, 0x200))

# Also check 0x3EAA00..0x3EAC00 in Ruby (another cluster)
print("\n" + "="*70)
print("RUBY: Hex dump of 0x3EAA00..0x3EAC00")
print("="*70)
print(hexdump(rom_ru, 0x3EAA00, 0x200))

# Check what the v6 scan found in FRLG around the trainer data area
# Let me also scan for any 8-byte stride table in FRLG around 0x3BA000-0x3C0000
print("\n" + "="*70)
print("FIRE RED: Scan for 8-byte stride pointer tables 0x3BA000..0x3C0000")
print("="*70)
for off in range(0x3BA000, 0x3C0000 - 8, 8):
    v = struct.unpack('<I', rom[off:off+4])[0]
    if BASE <= v < BASE + len(rom):
        # Found a pointer at stride 8 start
        # Check if next entries at +8, +16 etc. are also pointers
        count = 1
        for k in range(1, 100):
            nv = struct.unpack('<I', rom[off + k*8:off + k*8 + 4])[0]
            if BASE <= nv < BASE + len(rom):
                count += 1
            else:
                break
        if count >= 40:
            # Verify targets are PCS strings
            valid = True
            samples = []
            for k in range(min(5, count)):
                nv = struct.unpack('<I', rom[off + k*8:off + k*8 + 4])[0]
                doff = nv - BASE
                end = rom.find(b'\xff', doff)
                if end != -1 and end - doff <= 32:
                    txt = decode_pcs(rom[doff:end+1])
                    samples.append(txt)
                else:
                    valid = False
                    break
            if valid:
                print(f"  8-byte table at 0x{off:X}: {count} entries")
                for k, s in enumerate(samples):
                    nv = struct.unpack('<I', rom[off + k*8:off + k*8 + 4])[0]
                    print(f"    [{k}] 0x{nv-BASE:X} = {s}")
                break

# Also check for 4-byte stride tables in FRLG after location table
print("\n" + "="*70)
print("FIRE RED: Scan for 4-byte stride pointer tables 0x3BA000..0x3C0000")
print("="*70)
for off in range(0x3BA000, 0x3C0000 - 4, 4):
    v = struct.unpack('<I', rom[off:off+4])[0]
    if BASE <= v < BASE + len(rom):
        count = 1
        for k in range(1, 400):
            nv = struct.unpack('<I', rom[off + k*4:off + k*4 + 4])[0]
            if BASE <= nv < BASE + len(rom):
                count += 1
            else:
                break
        if count >= 40:
            # Check first
            nv = struct.unpack('<I', rom[off:off+4])[0]
            doff = nv - BASE
            end = rom.find(b'\xff', doff)
            if end != -1 and end - doff <= 32:
                txt = decode_pcs(rom[doff:end+1])
                if txt and any('\u30A0' <= c <= '\u30FF' for c in txt):
                    # Check a few more
                    names = []
                    for k in range(min(10, count)):
                        nv = struct.unpack('<I', rom[off + k*4:off + k*4 + 4])[0]
                        doff2 = nv - BASE
                        end2 = rom.find(b'\xff', doff2)
                        t = decode_pcs(rom[doff2:end2+1]) if end2 != -1 and end2 - doff2 <= 32 else "?"
                        names.append(t)
                    kata_ct = sum(1 for n in names if n and any('\u30A0' <= c <= '\u30FF' for c in n))
                    if kata_ct >= 5:
                        print(f"  4-byte table at 0x{off:X}: {count} entries")
                        for k, n in enumerate(names):
                            print(f"    [{k}] {n}")
                        print(f"    ... ({count} total)")
                        # Print a few more
                        for k in [count-3, count-2, count-1]:
                            nv = struct.unpack('<I', rom[off + k*4:off + k*4 + 4])[0]
                            doff2 = nv - BASE
                            end2 = rom.find(b'\xff', doff2)
                            t = decode_pcs(rom[doff2:end2+1]) if end2 != -1 and end2 - doff2 <= 32 else "?"
                            print(f"    [{k}] {t}")
                        break
