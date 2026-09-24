# -*- coding: utf-8 -*-
"""cells.py <tag> <bg> <r> <c0> <c1> — 按 map 逐格拼出屏上真实像素（2D ASCII）。
   横向每格 8 px，纵向上半取 map[r][c]、下半取 map[r+1][c]，共 16 行。"""
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag, bg = sys.argv[1], sys.argv[2]
r, c0, c1 = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
v = (T / ("drive_%s_vram.bin" % tag)).read_bytes()
LAYER = {"0": (30, 1), "2": (15, 2)}
sb, cb = LAYER[bg]
base = sb * 0x800
W = (c1 - c0 + 1) * 8
grid = [["." for _ in range(W)] for _ in range(16)]
nums = []

for k, c in enumerate(range(c0, c1 + 1)):
    eu = v[base + (r * 32 + c) * 2] | (v[base + (r * 32 + c) * 2 + 1] << 8)
    el = v[base + ((r + 1) * 32 + c) * 2] | (v[base + ((r + 1) * 32 + c) * 2 + 1] << 8)
    nums.append((eu & 0x3FF, el & 0x3FF))
    for half, n in enumerate((eu & 0x3FF, el & 0x3FF)):
        if not n:
            continue
        t = v[cb * 0x4000 + n * 32: cb * 0x4000 + n * 32 + 32]
        for y in range(8):
            for x in range(8):
                px = (t[y * 4 + (x >> 1)] >> ((x & 1) * 4)) & 0xF
                if px in (14, 15):
                    grid[y + half * 8][k * 8 + x] = "#"

print("cols c%d..c%d  upper/lower 号: %s" % (c0, c1, nums))
for y in range(16):
    print("".join(grid[y]))
