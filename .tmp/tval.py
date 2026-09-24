# -*- coding: utf-8 -*-
"""tval.py <tag> -- 池砖的像素值直方图 + ASCII 图（判「有没有写满/写的是谁」）。"""
import os
import struct
import sys
from collections import Counter

T = r"C:\code\GBA-Rom-Translator\.tmp"
tag = sys.argv[1]
lo = int(sys.argv[2]) if len(sys.argv) > 2 else 521
hi = int(sys.argv[3]) if len(sys.argv) > 3 else 560

v = open(os.path.join(T, "drive_%s_vram.bin" % tag), "rb").read()
io = open(os.path.join(T, "drive_%s_io.bin" % tag), "rb").read()
cnt = struct.unpack_from("<H", io, 0x08)[0]
cbase = ((cnt >> 2) & 3) * 0x4000


def pixels(t):
    off = cbase + t * 32
    out = []
    for y in range(8):
        row = []
        for x in range(8):
            b = v[off + y * 4 + x // 2]
            row.append((b & 0xF) if x % 2 == 0 else (b >> 4))
        out.append(row)
    return out


print("== 值直方图 %d..%d ==" % (lo, hi))
for t in range(lo, hi + 1):
    px = pixels(t)
    c = Counter(v2 for row in px for v2 in row)
    print("t%4d  %s" % (t, dict(sorted(c.items()))))

print("\n== ASCII（16 行 = t 与 t+1；'.'=0  '#'=1  ':'=8  ' '=15  其余=十六进制）==")
for t in range(lo, hi + 1, 2):
    print("--- t%d / t%d ---" % (t, t + 1))
    up, dn = pixels(t), pixels(t + 1)
    for y in range(8):
        print("   " + "".join("." if q == 0 else "#" if q == 1 else ":" if q == 8
                              else " " if q == 15 else "%X" % q for q in up[y]))
    for y in range(8):
        print("   " + "".join("." if q == 0 else "#" if q == 1 else ":" if q == 8
                              else " " if q == 15 else "%X" % q for q in dn[y]))
