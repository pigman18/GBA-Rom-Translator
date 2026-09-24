#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""解 0x08003630 / 0x080033B4 / 0x08003730 的跳转表内容。"""
import struct
ROM = r"C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba"
rom = open(ROM, "rb").read()
def u32(a): return struct.unpack_from("<I", rom, a-0x08000000)[0]

for name, tab in (("DrawGlyphTiles@0x08003630", 0x08003674),
                  ("twin@0x080033B4", 0x080033F8),
                  ("GetGlyphTilePointers@0x08003730", 0x0800374C),
                  ("InitWindowTileData?@0x08002A74", 0x08002A74)):
    print("=== %s  jump table @0x%08X ===" % (name, tab))
    for k in range(8):
        e = u32(tab + 4*k)
        ok = 0x08000000 <= e < 0x08000000 + len(rom)
        print("   [%d] = 0x%08X %s" % (k, e, "" if ok else "<非法/结束>"))
        if not ok: break
    print()
