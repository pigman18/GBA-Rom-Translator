# -*- coding: utf-8 -*-
"""dumpstr.py <hexaddr> <hexlen> -- 按「2 字节汉字 + FF 结尾」解码一段 ROM 文本区。"""
import sys
from pathlib import Path

rom = Path(r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()
a = int(sys.argv[1], 16)
n = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x200
o = a - 0x08000000
b = rom[o:o + n]
print("区段 %08X 起 %d 字节" % (a, n))
print("hex:", b[:64].hex(" "))
i = 0
cur = []
while i < len(b):
    c = b[i]
    if c == 0xFF:
        cur.append("|END")
        print("  @%08X  %s" % (a + i - len(cur) * 0 + 0, " ".join(cur)))
        cur = []
        i += 1
        continue
    if c == 0x00:
        cur.append("{}")
        i += 1
    elif c in (0xFA, 0xFB, 0xFC, 0xFD, 0xFE):
        cur.append("<%02X>" % c)
        i += 1
    elif c < 0x20:
        cur.append("\\%02X" % c)
        i += 1
    else:
        if i + 1 >= len(b):
            break
        cur.append("[%04X]" % ((b[i] << 8) | b[i + 1]))
        i += 2
