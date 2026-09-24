# -*- coding: utf-8 -*-
"""tilescan.py <tag> <lo> <hi> -- 每砖非零字节数 + 非零行位置（判断上下半砖是否存在）。"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
v = (T / ("drive_%s_vram.bin" % tag)).read_bytes()
io = (T / ("drive_%s_io.bin" % tag)).read_bytes()
cb = (struct.unpack_from("<H", io, 0x08)[0] >> 2) & 3
cbase = cb * 0x4000
print("cbase=%05X" % cbase)
for t in range(lo, hi):
    o = cbase + t * 32
    b = v[o:o + 32]
    nz = sum(1 for x in b if x)
    rows = [y for y in range(8) if any(b[y * 4:y * 4 + 4])]
    print("t%4d nz=%2d rows=%s" % (t, nz, rows))
