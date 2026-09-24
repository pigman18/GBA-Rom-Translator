# -*- coding: utf-8 -*-
"""把屏幕砖（8x16=64B）反解出来，在 ROM 全局搜（binary 形式）。"""
import numpy as np
from PIL import Image

SHOT = r"C:\Users\Administrator\.workbuddy\clipboard-images\clipboard-2026-09-22T08-34-54-307Z-4d6b3feb.png"
ROM = r"C:\code\GBA-Rom-Translator\roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba"

a = np.array(Image.open(SHOT).convert("RGB"))
g = a[54:214, 1:241]
WHITE = np.array([255, 255, 255]); BLUE = np.array([0x21, 0x84, 0xFF])
d_w = np.abs(g.astype(np.int16) - WHITE).sum(axis=2)
d_b = np.abs(g.astype(np.int16) - BLUE).sum(axis=2)
SCR = ((d_b <= 60) & (d_b < d_w))

rom = open(ROM, "rb").read()

def tile64(y0, x0):
    out = bytearray()
    for r in range(16):
        for c in range(0, 8, 2):
            lo = 1 if SCR[y0 + r, x0 + c] else 0
            hi = 1 if SCR[y0 + r, x0 + c + 1] else 0
            out.append((hi << 4) | lo)
    return bytes(out)

CASES = [
    ("band2#1 y42 x16", 42, 16),
    ("band2#1 y40 x16", 40, 16),   # 砖对齐备选
    ("band1#2 y26 x72", 26, 72),
    ("band1#1 y26 x16", 26, 16),
]
for tag, y0, x0 in CASES:
    pat = tile64(y0, x0)
    # binary 形式（任意非零 nibble 记 1）
    b1 = bytes(((1 if (b >> 4) else 0) << 4) | (1 if (b & 0x0F) else 0) for b in pat)
    print("\n=== %s ===" % tag)
    print("  raw   :", pat.hex())
    print("  binary:", b1.hex())
    for name, p in (("raw", pat), ("binary", b1)):
        hits, i = [], 0
        while True:
            i = rom.find(p, i)
            if i < 0:
                break
            hits.append(0x08000000 + i); i += 1
        print("  search[%s]: %d hits %s" % (name, len(hits), [hex(h) for h in hits[:6]]))
