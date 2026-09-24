#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""核对：日版是否真的没有 sGlyphMasks；0x082F1FC4 是什么。"""
import struct, os, glob
ROM = r"C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba"
rom = open(ROM, "rb").read()

print("=== 0x082F1FC4 附近 96 字节（0x60）===")
off = 0x2F1FC4
for k in range(0, 96, 16):
    chunk = rom[off+k:off+k+16]
    print("  0x%08X: %s" % (0x08000000+off+k, " ".join("%08X"%struct.unpack_from("<I",chunk,j)[0] for j in range(0,16,4))))

print("\n=== 全域搜索：连续 >=8 个 u32 全部形如 FFFFFxxx / 0000xxxx 的常量池 ===")
# 美版表首行特征 FFFFFFFF,FFFFFFFF,00000000
pats = {
  "FFFFFFFF FFFFFFFF 00000000": struct.pack("<3I",0xFFFFFFFF,0xFFFFFFFF,0),
  "0000000F FFFFFFFF FFFFFF00": struct.pack("<3I",0x0000000F,0xFFFFFFFF,0xFFFFFF00),
  "0FFFFFFF F0000000 00000000": struct.pack("<3I",0x0FFFFFFF,0xF0000000,0),
  "0FFFFFFF FF000000 00000000": struct.pack("<3I",0x0FFFFFFF,0xFF000000,0),
  "000000FF FFFFFFF0 00000000": struct.pack("<3I",0x000000FF,0xFFFFFFF0,0),
}
for label, p in pats.items():
    c = rom.count(p); print("  %-30s : %d 处" % (label, c))

# 美版是否有 ROM 可比对？
print("\n=== 本地是否有美版 ROM 可比对 ===")
for d in ("roms","roms/origin","roms/us","roms/usa"):
    p = os.path.join(r"C:\code\GBA-Rom-Translator", d)
    if os.path.isdir(p):
        for f in os.listdir(p): print("  ", os.path.join(d,f))
