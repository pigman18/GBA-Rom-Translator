# -*- coding: utf-8 -*-
"""slotlist.py 1539,1847,... -- 渲染指定槽（1bpp 大字库）为带槽号小图。"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

ROM = Path(r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()
BIG = 0x09500000 - 0x08000000
slots = [int(x, 0) for x in sys.argv[1].split(",")]
SC, W, ROWS, OFF = 8, 11, 11, 2
im = Image.new("RGB", (len(slots) * W * SC, (ROWS + 6) * SC), (18, 18, 22))
dr = ImageDraw.Draw(im)
for i, s in enumerate(slots):
    b = ROM[BIG + s * 16: BIG + (s + 1) * 16]
    for r in range(ROWS):
        for x in range(W):
            bi = r * W + x
            if (b[bi >> 3] >> (7 - (bi & 7))) & 1:
                for dy in range(SC):
                    for dx in range(SC):
                        im.putpixel((i * W * SC + x * SC + dx, (OFF + r) * SC + dy),
                                    (245, 245, 245))
    dr.text((i * W * SC + 3, ROWS * SC + 6), "0x%04X" % s, fill=(255, 220, 0))
    dr.line([(i * W * SC, 0), (i * W * SC, (ROWS + 6) * SC)], fill=(70, 70, 80))
out = "C:/code/GBA-Rom-Translator/.tmp/slotlist.png"
im.save(out)
print("saved", out, "slots:", ["0x%04X(%d)" % (s, s) for s in slots])
