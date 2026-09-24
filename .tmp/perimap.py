# -*- coding: utf-8 -*-
"""perimap.py <tag> -- 扫 0..1023 砖，标出「t == t+14」「t == t+12」「t == t+2」等关系，
定位周期结构的精确起止。"""
import os
import struct
import sys

T = r"C:\code\GBA-Rom-Translator\.tmp"
tag = sys.argv[1]
v = open(os.path.join(T, "drive_%s_vram.bin" % tag), "rb").read()
io = open(os.path.join(T, "drive_%s_io.bin" % tag), "rb").read()
cbase = ((struct.unpack_from("<H", io, 0x08)[0] >> 2) & 3) * 0x4000


def raw(t):
    return v[cbase + t * 32: cbase + t * 32 + 32]


for p in (2, 4, 8, 12, 14, 16, 28):
    same = [t for t in range(0, 1024 - p) if raw(t) and raw(t) == raw(t + p)]
    # 压缩为区间
    runs = []
    for t in same:
        if runs and t == runs[-1][1] + 1:
            runs[-1][1] = t
        else:
            runs.append([t, t])
    print("周期 %2d: 相同砖数=%4d  区间=%s" % (p, len(same), runs[:14]))

print()
print("== 各砖是否非空（0..1023，'#'=非空 '.'=空）==")
for base in range(0, 1024, 64):
    line = "".join("#" if any(raw(t)) else "." for t in range(base, base + 64))
    print("%4d %s" % (base, line))
