# -*- coding: utf-8 -*-
"""mapdump.py <tag> [r0 r1 c0 c1] — 打印某页 BG0/BG2 的 tilemap 行段（号 + 属性位）。
   号 = entry & 0x3FF；pal = (entry>>12)&0xF；prio = (entry>>10)&3。"""
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag = sys.argv[1]
v = (T / ("drive_%s_vram.bin" % tag)).read_bytes()

# BGxCNT 值由 an_bgs.py 实测：BG0=0x1E06 -> sb=30, cb=1 ; BG2=0x0F08 -> sb=15, cb=2
LAYER = {"0": (30, 1), "2": (15, 2)}

args = sys.argv[2:]
if args:
    bg = args[0]
    r0, r1, c0, c1 = (int(x) for x in args[1:5])
else:
    bg, r0, r1, c0, c1 = "0", 0, 31, 0, 31

sb, cb = LAYER[bg]
base = sb * 0x800
print("BG%s screenBase=%d (0x%05X) charBase=%d" % (bg, sb, 0x06000000 + base, cb))
for r in range(r0, r1 + 1):
    line = []
    for c in range(c0, c1 + 1):
        off = base + (r * 32 + c) * 2
        e = v[off] | (v[off + 1] << 8)
        n = e & 0x3FF
        line.append("%3d" % n if n else "  .")
    if args:
        print("r%02d " % r + " ".join(line))
    else:
        nz = [x for x in line if x.strip() != "."]
        if nz:
            print("r%02d " % r + " ".join(line))
