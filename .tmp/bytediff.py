# -*- coding: utf-8 -*-
"""bytediff.py <tag> <tileA> <tileB> [blk_hex] — 逐行打印两块砖的 4 个 byte 十六进制。"""
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag, ta, tb = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
VOFF = int(sys.argv[4], 16) if len(sys.argv) > 4 else 0x4000
vram = (T / ("drive_%s_vram.bin" % tag)).read_bytes()


def tile(n):
    return vram[VOFF + n * 32:VOFF + n * 32 + 32]


A, B = tile(ta), tile(tb)
print("row |  tile%-4d byte0..3        |  tile%-4d byte0..3" % (ta, tb))
for r in range(8):
    a = A[r * 4:r * 4 + 4]
    b = B[r * 4:r * 4 + 4]
    mark = "  " if a == b else " *"
    print(" %2d |  %s   |  %s%s" % (r, " ".join("%02X" % v for v in a),
                                     " ".join("%02X" % v for v in b), mark))
