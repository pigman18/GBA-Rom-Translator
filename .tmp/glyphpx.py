# -*- coding: utf-8 -*-
"""glyphpx.py — 把指定砖号对(t,t+1)打成 ASCII 点阵，量出原版字形实际占几列。
用法: python glyphpx.py org2 53 43 25 51 1 5
"""
import os, re, struct, sys

T = r"C:\code\GBA-Rom-Translator\.tmp"
TAG = sys.argv[1]
TILES = [int(x) for x in sys.argv[2:]]
v = open(os.path.join(T, "drive_%s_vram.bin" % TAG), "rb").read()
txt = open(os.path.join(T, "drive_%s.log" % TAG), encoding="utf-8", errors="replace").read()
io = {m.group(1): int(m.group(2), 16)
      for m in re.finditer(r"\[io\] IO (\w+) 0x[0-9a-fA-F]+:\s*(0x[0-9a-fA-F]+)", txt)}
cbase = ((io["BG0CNT"] >> 2) & 3) * 0x4000


def colr(t):
    out = []
    for y in range(16):
        tt = t + (0 if y < 8 else 1)
        yy = y % 8
        row = ""
        for x in range(8):
            b = v[cbase + tt * 32 + yy * 4 + x // 2]
            idx = (b & 0xF) if x % 2 == 0 else (b >> 4)
            row += "#" if idx else "."
        out.append(row)
    return out


for t in TILES:
    cs = colr(t)
    print("=== 砖号 %d/%d  (每列墨点数: %s) ==="
          % (t, t + 1, " ".join(str(sum(1 for y in range(16) if cs[y][x] == "#"))
                                for x in range(8))))
    for y in range(16):
        print("   " + cs[y])
    print()
