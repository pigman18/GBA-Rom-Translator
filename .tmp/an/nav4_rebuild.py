# -*- coding: utf-8 -*-
"""重建：把屏幕 tile 按"每 bit -> 1 字节(低 nibble)"的模型反推源 1bpp 8x8 字形，整行拼出来。"""
import numpy as np
a = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\shot_native.npy").astype(int)
blue = (np.abs(a - np.array([33, 132, 255])).sum(axis=2) < 60)

def tile_bytes(x0, y0):
    """屏幕 8x8 -> 4bpp 32 字节（墨 = 0xF nibble）"""
    out = bytearray()
    for y in range(y0, y0 + 8):
        for i in range(4):
            lo = 0xF if blue[y, x0 + 2 * i] else 0
            hi = 0xF if blue[y, x0 + 2 * i + 1] else 0
            out.append((hi << 4) | lo)
    return bytes(out)

def reconstruct(x0, y0top):
    """两个上下 tile 的偶数列 -> 源 8x8（1bpp，MSB-first，每字节 1 行）"""
    bits = []
    for (yy, xx) in ((y0top, x0), (y0top + 8, x0)):
        pass
    # 按推导：屏幕行 Y 的偶数列 4 个 = 源代码 bit 4*Yrel .. 4*Yrel+3
    src = bytearray(8)
    for Yrel in range(16):
        Y = y0top + Yrel
        for k in range(4):
            if blue[Y, x0 + 2 * k]:
                idx = Yrel * 4 + k          # 源代码中的 bit 序号（0..63, MSB-first）
                src[idx // 8] |= (0x80 >> (idx % 8))
    return bytes(src)

def show(b):
    for y in range(8):
        print("      " + "".join("#" if (b[y] >> (7 - x)) & 1 else "." for x in range(8)))

print("=" * 78)
print("第一行文字带：上 tile y=24..31，下 tile y=32..39")
for x0 in range(8, 152, 8):
    b = reconstruct(x0, 24)
    n = sum(bin(v).count("1") for v in b)
    tag = "←" if n else ""
    print("\n  tile x=%d  (源墨 %d)  hex=%s %s" % (x0, n, b.hex(), tag))
    if n:
        show(b)

print("\n" + "=" * 78)
print("第二行文字带：上 tile y=40..47，下 tile y=48..55")
for x0 in range(8, 152, 8):
    b = reconstruct(x0, 40)
    n = sum(bin(v).count("1") for v in b)
    print("\n  tile x=%d  (源墨 %d)  hex=%s" % (x0, n, b.hex()))
    if n:
        show(b)
