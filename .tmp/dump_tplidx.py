# -*- coding: utf-8 -*-
"""dump 0x081BB8C0..0x081BBA80 区域，看清模板表后面的索引结构。"""
import os
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba")
BASE = 0x08000000
rom = open(ROM, "rb").read()

hdr = "%-10s  %-9s %-9s  %-9s %-9s  %s" % ("addr", "u32#0", "u32#1", "u16#0", "u16#1", "ascii")
print(hdr)
print("-" * len(hdr))
for a in range(0x081BB8C0, 0x081BBA80, 8):
    o = a - BASE
    w0, w1 = struct.unpack_from("<II", rom, o)
    h0, h1 = struct.unpack_from("<HH", rom, o)
    txt = "".join(chr(c) if 32 <= c < 127 else "." for c in rom[o:o + 8])
    pl = ""
    if 0x081BB3DC <= w0 < 0x081BB8BC:
        pl = "  ->tpl %08X (idx %d)" % (w0, (w0 - 0x081BB3DC) // 0x18)
    print("%08X  %08X %08X  %04X %04X  %s%s" % (a, w0, w1, h0, h1, txt, pl))

print()
print("=== 模板表本身（步长 0x18）逐条：模板地址 / +0C tileData / +10 tilemap ===")
for a in range(0x081BB3DC, 0x081BB8C0, 0x18):
    o = a - BASE
    td = struct.unpack_from("<I", rom, o + 0x0C)[0]
    mp = struct.unpack_from("<I", rom, o + 0x10)[0]
    print("%08X idx%2d tm=%d font=%d  tileData=%08X tilemap=%08X  raw8=%s"
          % (a, (a - 0x081BB3DC) // 0x18, rom[o + 9], rom[o + 8], td, mp,
             " ".join("%02X" % c for c in rom[o:o + 8])))
