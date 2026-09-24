# -*- coding: utf-8 -*-
"""slotscan.py <tag> <lo> <ncol> -- 逐 x 扫 11x11 窗口，两种墨色模式都试：
 ink=1 区：观测 '值==1'；ink=8 区：观测 '值==8' 对比『墨+阴影并集』。
凡 d=0 即「该处确实画了字库某槽」，输出槽号 + x + 该字单元值分布。"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
ROM = Path(r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()
BIG = 0x09500000 - 0x08000000


def ink_mask(s):
    b = ROM[BIG + s * 16: BIG + (s + 1) * 16]
    return [[(b[(r * 11 + x) >> 3] >> (7 - ((r * 11 + x) & 7))) & 1 for x in range(11)]
            for r in range(11)]


def union_mask(m):
    return tuple(1 if (m[r][c] or (r >= 1 and c >= 1 and m[r - 1][c - 1])) else 0
                 for r in range(11) for c in range(11))


def flat(m):
    return tuple(q for row in m for q in row)


LIBS = [ink_mask(s) for s in range(0x2000)]
LIB_INK = [flat(m) for m in LIBS]
LIB_UNI = [union_mask(m) for m in LIBS]

tag, lo, ncol = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
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

print("map 列 -> 砖对：")
for c in range(ncol):
    print("   col%-2d  x=%3d..%3d  砖 %d,%d" % (c, c * 8, c * 8 + 7, lo + 2 * c, lo + 2 * c + 1))
print()
for mode in ("ink1", "ink8union"):
    want = 1 if mode == "ink1" else 8
    libs = LIB_INK if mode == "ink1" else LIB_UNI
    print("== 模式 %s ==" % mode)
    for x in range(0, W - 11 + 1):
        obs = tuple(1 if band[2 + r][x + c] == want else 0 for r in range(11) for c in range(11))
        n = sum(obs)
        if n == 0:
            continue
        d, s = min((sum(1 for a, b in zip(obs, lib) if a != b), i) for i, lib in enumerate(libs))
        if d <= 1:
            print("  x=%3d 墨点=%3d 槽%04X d=%d" % (x, n, s, d))
    print()
