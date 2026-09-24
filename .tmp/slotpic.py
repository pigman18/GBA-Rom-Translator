# -*- coding: utf-8 -*-
"""slotpic.py <lo> <hi> [--big|--small|--mid] -- 把 1bpp 字库一段槽渲染成带号小图。"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

ROM = Path(r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()
BASE = {"big": (0x09500000, 11, 11, 16, 2), "mid": (0x09700000, 9, 11, 13, 2),
        "small": (0x09600000, 9, 9, 11, 5)}
kind = "big"
for k in BASE:
    if "--" + k in sys.argv:
        kind = k
args = [a for a in sys.argv[1:] if not a.startswith("--")]
lo, hi = int(args[0]), int(args[1])
addr, W, ROWS, STRIDE, OFF = BASE[kind]
off0 = addr - 0x08000000

SC = 6
COLS = 12
n = hi - lo + 1
rows = (n + COLS - 1) // COLS
im = Image.new("RGB", (COLS * W * SC, rows * (ROWS * SC + 16)), (18, 18, 22))
dr = ImageDraw.Draw(im)
for i, s in enumerate(range(lo, hi + 1)):
    b = ROM[off0 + s * STRIDE: off0 + s * STRIDE + STRIDE]
    gx, gy = i % COLS, i // COLS
    for r in range(ROWS):
        for x in range(W):
            bi = r * W + x
            bit = (b[bi >> 3] >> (7 - (bi & 7))) & 1 if (bi >> 3) < len(b) else 0
            if bit:
                for dy in range(SC):
                    for dx in range(SC):
                        im.putpixel((gx * W * SC + x * SC + dx,
                                     gy * (ROWS * SC + 16) + (OFF + r) * SC + dy),
                                    (240, 240, 240))
    dr.text((gx * W * SC + 2, gy * (ROWS * SC + 16) + ROWS * SC + 2), "%d" % s,
            fill=(255, 220, 0))
out = "C:/code/GBA-Rom-Translator/.tmp/slots_%s_%d_%d.png" % (kind, lo, hi)
im.save(out)
print("saved", out, im.size)
print("live string slots:", [(c, c & 0x1FFF) for c in (0xFC05, 0x0F05, 0x0F02)])
