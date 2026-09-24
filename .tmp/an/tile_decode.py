# -*- coding: utf-8 -*-
"""屏幕 -> 4bpp 砖反解 + ROM 全局搜。
判定：屏幕文字区只有 2 色（白 bg + 蓝 fg）=> 二值化 => 4bpp 砖 32 字节。
"""
import numpy as np
from PIL import Image

SHOT = r"C:\Users\Administrator\.workbuddy\clipboard-images\clipboard-2026-09-22T08-34-54-307Z-4d6b3feb.png"
ROM = r"C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba"
OUT = r"C:\code\GBA-Rom-Translator\.tmp\an"

a = np.array(Image.open(SHOT).convert("RGB"))
g = a[54:214, 1:241]
H, W = 160, 240

WHITE = np.array([255, 255, 255])
BLUE = np.array([0x21, 0x84, 0xFF])
d_w = np.abs(g.astype(np.int16) - WHITE).sum(axis=2)
d_b = np.abs(g.astype(np.int16) - BLUE).sum(axis=2)
ink = (d_b <= 60) & (d_b < d_w)          # 蓝 = 墨
bgm = (d_w <= 60)                        # 白 = 底

def tile_bytes(y0, x0):
    """读一个 8x8 砖 -> 32 字节 4bpp（fg nibble=1, bg=0）。"""
    out = bytearray()
    for r in range(8):
        for c in range(0, 8, 2):
            lo = 1 if ink[y0 + r, x0 + c] else 0
            hi = 1 if ink[y0 + r, x0 + c + 1] else 0
            out.append((hi << 4) | lo)
    return bytes(out)

def show(y0, x0, tag):
    print("  %s  y=%d x=%d" % (tag, y0, x0))
    for r in range(8):
        print("    " + "".join("#" if ink[y0 + r, x0 + c] else "." for c in range(8)))
    print("    hex: " + tile_bytes(y0, x0).hex())

print("=== band y=26..33 (upper tile) x=16.. ===")
for x0 in range(16, 72, 8):
    show(26, x0, "t%d" % ((x0 - 16) // 8))

print("\n=== band y=34..41 x=16.. ===")
for x0 in range(16, 72, 8):
    show(34, x0, "t%d" % ((x0 - 16) // 8))

# ---- ROM 全局搜 ----
rom = open(ROM, "rb").read()
print("\nROM size = %d" % len(rom))
pat = tile_bytes(26, 16)
print("search pattern (tile y26 x16) =", pat.hex())
idx = 0
hits = []
while True:
    i = rom.find(pat, idx)
    if i < 0:
        break
    hits.append(0x08000000 + i)
    idx = i + 1
print("hits: %d" % len(hits))
for h in hits[:20]:
    print("   0x%08X" % h)
