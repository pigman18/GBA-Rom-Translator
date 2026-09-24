# -*- coding: utf-8 -*-
"""交付 ROM 里的字库本体检查：0x09400000 起，128B/字，前 64B = 上砖+下砖。"""
import os
import numpy as np
from PIL import Image

ROMS = [
    r"C:\code\GBA-Rom-Translator\roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba",
    r"C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba",
]
OUT = r"C:\code\GBA-Rom-Translator\.tmp\an"

for ROM in ROMS:
    if not os.path.exists(ROM):
        print("missing:", ROM); continue
    d = open(ROM, "rb").read()
    print("\n==== %s  size=%d (0x%X)" % (os.path.basename(ROM), len(d), len(d)))
    off = 0x09400000 - 0x08000000
    print("off 0x%X in range: %s" % (off, off < len(d)))
    if off + 256 > len(d):
        continue
    head = d[off:off + 64]
    print("0x09400000[0:64] =", head.hex())
    print("  nibble 统计:", {hex(v): head.count(v) for v in set(head)})

    # 渲染前 16 个字（128B/字，只画前 64B = 8x16）
    n = 16
    img = np.zeros((16 * n, 8), dtype=np.uint8)
    for gi in range(n):
        raw = d[off + gi * 128: off + gi * 128 + 64]
        for r in range(16):
            for c in range(8):
                b = raw[r * 4 + c // 2]
                nib = (b >> 4) if (c % 2) else (b & 0x0F)
                img[gi * 16 + r, c] = 255 if nib else 0
    im = Image.fromarray(img).resize((8 * 12, 16 * n * 12), Image.NEAREST)
    p = OUT + r"\romlib_%s.png" % os.path.basename(ROM)[:14]
    im.save(p)
    print("saved", p)
