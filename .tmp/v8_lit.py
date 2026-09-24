#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""追 DrawGlyphTile 家族的真正 RMW 混合核心与宽度相关表。"""
import struct
ROM = r"C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba"
rom = open(ROM, "rb").read()
def u8(a): return rom[a-0x08000000]
def u16(a): return struct.unpack_from("<H", rom, a-0x08000000)[0]
def u32(a): return struct.unpack_from("<I", rom, a-0x08000000)[0]

def literals(start, end, label):
    print("=== %s 字面量池 (0x%08X-0x%08X) ===" % (label, start, end))
    out = []
    for a in range(start, end, 2):
        hw = u16(a)
        if (hw >> 11) == 0b01001:
            rd = (hw >> 8) & 7
            imm = (hw & 0xFF) * 4
            lit = ((a + 4) & ~3) + imm
            if 0x08000000 <= lit < 0x08000000 + len(rom) - 4:
                v = u32(lit)
                print("  0x%08X: ldr r%d,[pc] -> 0x%08X = 0x%08X" % (a, rd, lit, v))
                out.append(v)
    return out

# DrawGlyphTiles(0x08003630) 的池
literals(0x08003630, 0x080036DC, "DrawGlyphTiles 0x08003630")
print()
literals(0x080033B4, 0x08003464, "twin 0x080033B4")
print()
literals(0x08003830, 0x080038A0, "0x08003830")
print()
literals(0x080038A0, 0x08003938, "0x080038A0")

print("\n=== 0x081BB3D8 处 4 字节表 (用于 0x08003AC2) ===")
for k in range(8): print("  +%d = %02X" % (k, u8(0x081BB3D8+k)))
print("=== 0x081B4?/0x081B49AC 等表 ===")
for a in (0x081B49AC, 0x081B3AAC, 0x081B34A8):
    print("  0x%08X 前 32 字节: %s" % (a, " ".join("%02X"%u8(a+k) for k in range(32))))
