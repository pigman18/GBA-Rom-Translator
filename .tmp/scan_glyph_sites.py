# -*- coding: utf-8 -*-
"""扫描全 ROM：bl 0x08003630(DrawGlyphTiles) / bl 0x08003830(DrawGlyphTile_Unsh)
   / bl 0x080038A0(DrawGlyphTile_Shad) / bl 0x08003730(GetGlyphTilePointers)
   并列出每个调用点所在函数的起始地址。"""
import struct, sys
ROM = 'work/POKEMON_RUBY_AXVJ00/build/baserom.gba'
rom = open(ROM,'rb').read()
BASE = 0x08000000

def scan_bl(targets):
    hits = {}
    for off in range(0, len(rom)-4, 2):
        hw1, hw2 = struct.unpack_from('<HH', rom, off)
        if (hw1 & 0xF800) != 0xF000:      # BL 第一半字
            continue
        if (hw2 & 0xD000) != 0xD000:      # J1=1 J2=1
            continue
        S  = (hw1 >> 10) & 1
        imm10 = hw1 & 0x3FF
        J1 = (hw2 >> 13) & 1
        J2 = (hw2 >> 11) & 1
        imm11 = hw2 & 0x7FF
        I1 = (~(J1 ^ S)) & 1
        I2 = (~(J2 ^ S)) & 1
        imm32 = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
        if imm32 >= (1 << 25):
            imm32 -= (1 << 26)
        pc = BASE + off + 4
        tgt = pc + imm32
        if tgt in targets:
            hits.setdefault(tgt, []).append(BASE + off)
    return hits

TARGETS = {0x08003630:'DrawGlyphTiles', 0x08003830:'DrawGlyphTile_Unshadowed',
           0x080038A0:'DrawGlyphTile_Shadowed', 0x08003730:'GetGlyphTilePointers',
           0x08002A50:'InitWindowTileData', 0x08002A8C:'tm_font_1_4',
           0x08002AAC:'tm_font_2_3', 0x08002ACC:'tm_font_5_6'}

# 建立函数边界：扫所有 push {...lr} 的地址作为候选函数头
hits = scan_bl(set(TARGETS))
for tgt, sites in sorted(hits.items()):
    print('== %s @%08X : %d 处' % (TARGETS[tgt], tgt, len(sites)))
    for s in sites:
        print('     %08X' % s)
