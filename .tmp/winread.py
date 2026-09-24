# -*- coding: utf-8 -*-
"""winread.py <tag> -- 从 EWRAM dump 读窗口结构 + 跟随字符串指针，打出真实文本。"""
import os
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag = sys.argv[1]
ew = (T / f"drive_{tag}_ewram.bin").read_bytes()      # 0x02000000 起
rom = Path(r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()

EWB = 0x02000000


def u8(a):
    return ew[a - EWB]


def u16(a):
    return struct.unpack_from("<H", ew, a - EWB)[0]


def u32(a):
    return struct.unpack_from("<I", ew, a - EWB)[0]


WIN = 0x0202E658
print("== window @ %08X ==" % WIN)
for off in range(0, 0x28, 2):
    print("  +%02X = %04X" % (off, u16(WIN + off)))
print("  tm(+0A)=%d font(+0B)=%d C=0x%02X D=0x%02X E=0x%02X pal=%d"
      % (u8(WIN + 0x0A) & 0xFF, u8(WIN + 0x0B),
         u8(WIN + 0x0C), u8(WIN + 0x0D), u8(WIN + 0x0E), u8(WIN + 0x0F)))
print("  tpl(+00)=%08X textPtr(+10)=%08X textIdx(+14)=%04X"
      % (u32(WIN), u32(WIN + 0x10), u16(WIN + 0x14)))
print("  TILE_BASE=%04X OFFSET=%04X CUR_X=%d CUR_TX=%d CUR_Y=%d CUR_TY=%d TILEDATA=%08X"
      % (u16(WIN + 0x16), u16(WIN + 0x18), u8(WIN + 0x1A), u8(WIN + 0x1B),
         u8(WIN + 0x1C), u8(WIN + 0x1D), u32(WIN + 0x20)))

# 跟随字符串指针
p = u32(WIN + 0x10)
print("\n== string @ %08X ==" % p)
if 0x08000000 <= p < 0x0A000000:
    o = p - 0x08000000
    if o < len(rom):
        raw = rom[o:o + 64]
        print("  raw:", raw.hex(" "))
        # 解 \XX 转义 + 高字节编码的汉字
        i = 0
        out = []
        while i < len(raw):
            b = raw[i]
            if b == 0xFF:
                break
            if b == 0x00:
                out.append("\\00")
            elif b == 0xFC:
                out.append("<FC>")
            elif b == 0xFB:
                out.append("<FB>")
            elif b == 0xFA:
                out.append("<FA>")
            elif b == 0xFE:
                out.append("<FE>")
            elif b < 0x20 and b != 0x0A:
                out.append("\\%02X" % b)
            elif b >= 0x20:
                # 汉字：两字节 (lead<<8)|trail
                if i + 1 < len(raw):
                    code = (raw[i] << 8) | raw[i + 1]
                    out.append("[C:{%04X idx=%04X}]" % (code, code & 0x1FFF))
                    i += 2
                    continue
                else:
                    out.append("%02X" % b)
            i += 1
        print("  seq:", " ".join(out))
else:
    print("  (不是 ROM 指针)")
