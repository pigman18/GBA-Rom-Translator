# -*- coding: utf-8 -*-
"""glyphscan.py <tag> <lo> <ncol> <ink> -- 在像素带上逐 x 扫 11x11 窗口，
凡与字库某槽完全一致(d=0)就报告 => 得到真实字起点与槽序列。"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
ROM = Path(r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()
BIG = 0x09500000 - 0x08000000


def slot_bits(s):
    b = ROM[BIG + s * 16: BIG + (s + 1) * 16]
    return tuple((b[(r * 11 + x) >> 3] >> (7 - ((r * 11 + x) & 7))) & 1
                 for r in range(11) for x in range(11))


LIB = [slot_bits(s) for s in range(0x2000)]

tag, lo, ncol, ink = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
v = (T / f"drive_{tag}_vram.bin").read_bytes()
io = (T / f"drive_{tag}_io.bin").read_bytes()
cbase = ((struct.unpack_from("<H", io, 0x08)[0] >> 2) & 3) * 0x4000

W = ncol * 8
band = [[0] * W for _ in range(16)]
for c in range(ncol):
    for half in (0, 1):
        t = lo + 2 * c + half
        off = cbase + t * 32
        for y in range(8):
            for x in range(8):
                b = v[off + y * 4 + x // 2]
                band[half * 8 + y][c * 8 + x] = (b & 0xF) if x % 2 == 0 else (b >> 4)

print("== 带（#=墨%d :=影8 .=底15）==" % ink)
for r in range(16):
    print("%2d " % r + "".join("#" if q == ink else ":" if q == 8 else "." if q == 15
                               else "?" if q == 0 else "%X" % q for q in band[r]))

print("\n== 逐 x 扫 11x11（行 2..12）==")
hits = []
for x in range(0, W - 11 + 1):
    m = tuple(1 if band[2 + r][x + c] == ink else 0 for r in range(11) for c in range(11))
    n = sum(m)
    if n == 0:
        hits.append((x, -1, 0, 0))
        continue
    d, s = min((sum(1 for a, b in zip(m, lib) if a != b), i) for i, lib in enumerate(LIB))
    hits.append((x, s, d, n))
for x, s, d, n in hits:
    tag2 = ""
    if d == 0 and n > 0:
        tag2 = "  <<< 完全一致 槽%04X 墨点=%d" % (s, n)
    elif n == 0:
        tag2 = "  (空)"
    print("  x=%3d 墨点=%3d 最近槽%04X d=%3d%s" % (x, n, s, d, tag2))
