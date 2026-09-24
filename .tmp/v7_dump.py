#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""精确 dump：3830 / 38A0 / 3930 / 3A30 的原始字节，供人工比对。"""
import struct
ROM = r"C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba"
rom = open(ROM, "rb").read()
def u32(a): return struct.unpack_from("<I", rom, a-0x08000000)[0]

for name, a in (("0x08003830",0x08003830),("0x080038A0",0x080038A0),
                ("0x08003930",0x08003930),("0x080039D8",0x080039D8),
                ("0x08003A30",0x08003A30),("0x08003A40",0x08003A40),
                ("0x08003AA8",0x08003AA8)):
    off = a - 0x08000000
    print("%s 前 4 字节: %s" % (name, " ".join("%02X"%b for b in rom[off:off+4])))

print("\n=== 0x08003830 前 8 条指令 ===")
for k in range(0, 16, 2):
    print("  0x%08X: %04X" % (0x08003830+k, struct.unpack_from("<H", rom, 0x3830+k)[0]))

print("\n=== 0x08003A30 前 12 条指令 ===")
for k in range(0, 24, 2):
    print("  0x%08X: %04X" % (0x08003A30+k, struct.unpack_from("<H", rom, 0x3A30+k)[0]))

print("\n=== 3830 里 ldr [pc,#n] 字面量解析 ===")
for a in range(0x08003830, 0x080038A0, 2):
    hw = struct.unpack_from("<H", rom, a-0x08000000)[0]
    if (hw>>11) == 0b01001:
        rd=(hw>>8)&7; imm=(hw&0xFF)*4
        lit = a+4+imm
        # Thumb: pc 对齐到 4
        lit = ((a+4) & ~3) + imm
        print("  0x%08X: ldr r%d,[pc,#%d] -> 0x%08X = 0x%08X"
              % (a, rd, imm, lit, u32(lit)))

print("\n=== 38A0 里 ldr [pc,#n] 字面量解析 ===")
for a in range(0x080038A0, 0x08003938, 2):
    hw = struct.unpack_from("<H", rom, a-0x08000000)[0]
    if (hw>>11) == 0b01001:
        rd=(hw>>8)&7; imm=(hw&0xFF)*4
        lit = ((a+4) & ~3) + imm
        print("  0x%08X: ldr r%d,[pc,#%d] -> 0x%08X = 0x%08X"
              % (a, rd, imm, lit, u32(lit)))
