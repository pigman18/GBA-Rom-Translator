# -*- coding: utf-8 -*-
"""rowview.py <tag> <bg> <row> <c0> <c1> [scale] — 按 tilemap 逐格还原一行可见像素"""
import re, sys
from pathlib import Path
from PIL import Image
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag, bg, row, c0, c1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
sc = int(sys.argv[6]) if len(sys.argv) > 6 else 8
txt = (T / ("drive_%s.log" % tag)).read_text(encoding="utf-8", errors="replace")
reg = {}
for m in re.finditer(r"IO (\w+) 0x[0-9a-f]+:\s*(0x[0-9a-fA-F]+)", txt):
    reg[m.group(1)] = int(m.group(2), 16)
cnt = reg["BG%dCNT" % bg]
cb = (cnt >> 2) & 3
sb = (cnt >> 8) & 0x1F
v = (T / ("drive_%s_vram.bin" % tag)).read_bytes()
m8 = v[sb * 0x800: sb * 0x800 + 0x800]
base = cb * 0x4000
W = (c1 - c0) * 8
img = Image.new("L", (W, 16), 255)
cells = []
for i, c in enumerate(range(c0, c1)):
    off = (row * 32 + c) * 2
    w = m8[off] | (m8[off + 1] << 8)
    t = w & 0x3FF
    cells.append(t)
    to = base + t * 32
    tl = v[to:to + 32]
    for r in range(8):
        rowb = tl[r * 4:r * 4 + 4]
        for ci in range(8):
            b = rowb[ci // 2]
            val = (b & 0xF) if ci % 2 == 0 else (b >> 4)
            img.putpixel((i * 8 + ci, r), 255 - val * 17)
    # 第二行（+0x40 下一行）用 t+1 的图块
    to2 = base + (t + 1) * 32
    tl2 = v[to2:to2 + 32]
    for r in range(8):
        rowb = tl2[r * 4:r * 4 + 4]
        for ci in range(8):
            b = rowb[ci // 2]
            val = (b & 0xF) if ci % 2 == 0 else (b >> 4)
            img.putpixel((i * 8 + ci, 8 + r), 255 - val * 17)
print("cells:", " ".join(str(x) for x in cells))
img.resize((W * sc, 16 * sc), Image.NEAREST).save(T / ("rowview_%s_bg%d_r%d.png" % (tag, bg, row)))
print(T / ("rowview_%s_bg%d_r%d.png" % (tag, bg, row)))
