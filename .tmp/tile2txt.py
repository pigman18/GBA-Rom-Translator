# -*- coding: utf-8 -*-
"""tile2txt.py <tag> <absHexAddr> <n> — 把连续 n 个 tile 以 8x8 ASCII 打印（4bpp，低 nibble=左像素）"""
import sys
from pathlib import Path
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag = sys.argv[1]
addr = int(sys.argv[2], 16)
n = int(sys.argv[3])
v = (T / ("drive_%s_vram.bin" % tag)).read_bytes()
off = addr - 0x06000000
for k in range(n):
    t = v[off + k * 32: off + k * 32 + 32]
    print("tile@0x%08X (#%d)" % (addr + k * 32, off // 32 + k))
    for r in range(8):
        line = ""
        for c in range(4):
            b = t[r * 4 + c]
            line += "%X%X" % (b & 0xF, b >> 4)
        print("   " + line.replace("0", "."))
