# -*- coding: utf-8 -*-
"""把屏幕 tile 的位图转成各种格式，在 ROM 里全局搜索，定位它的来源。"""
import numpy as np
from pathlib import Path

ROOT = Path(r"C:\code\GBA-Rom-Translator")
rom = np.fromfile(ROOT / "roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba", dtype=np.uint8)
rb = rom.tobytes()
BASE = 0x08000000
print("ROM 大小", len(rb))

a = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\shot_native.npy").astype(int)
blue = (np.abs(a - np.array([33, 132, 255])).sum(axis=2) < 60)

def bmp(x0, y0, w=8, h=8):
    return [[1 if blue[y0 + y, x0 + x] else 0 for x in range(w)] for y in range(h)]

def occ(pat, limit=8):
    out = []; st = 0
    while len(out) < limit:
        k = rb.find(pat, st)
        if k < 0: break
        out.append(k + BASE); st = k + 1
    return out

def report(name, pat, limit=8):
    o = occ(pat, limit)
    print("  %-34s len=%3d  出现 %d 处 %s" % (name, len(pat), len(o),
          [hex(x) for x in o[:5]]))

# 取几个 tile
for tag, x0, y0 in (("t(x16,y24)", 16, 24), ("t(x24,y24)", 24, 24),
                    ("t(x72,y24)", 72, 24), ("t(x128,y24)", 128, 24)):
    b = bmp(x0, y0)
    print("\n=== %s ===" % tag)
    for r in b:
        print("    " + "".join("#" if v else "." for v in r))
    # 1) 4bpp 32 字节（正常布局，墨 = 0xF）
    bb = bytearray()
    for y in range(8):
        for i in range(4):
            lo = 0xF if b[y][2 * i] else 0
            hi = 0xF if b[y][2 * i + 1] else 0
            bb.append((hi << 4) | lo)
    report("4bpp 32B (墨0xF)", bytes(bb))
    # 2) 1bpp 8 字节（每行 1 字节，MSB 最左）
    b1 = bytearray()
    for y in range(8):
        v = 0
        for x in range(8):
            if b[y][x]: v |= 0x80 >> x
        b1.append(v)
    report("1bpp 8B (MSB left)", bytes(b1))
    # 3) 1bpp 8B 但只取偶数列（压缩 4 列 -> 每行 1 字节的高 4 位）
    b2 = bytearray()
    for y in range(8):
        v = 0
        for k in range(4):
            if b[y][2 * k]: v |= 0x80 >> k
        b2.append(v)
    report("1bpp 8B 偶列压缩到高4位", bytes(b2))
    # 4) "每 bit 1 字节"展开的源：源代码 = 每行 4 列有效
    src = bytearray()
    for Yrel in range(8):
        v = 0
        for k in range(4):
            if b[Yrel][2 * k]: v |= 0x80 >> k
        src.append(v)
    report("源代码 8B（每行4像素）", bytes(src))
    # 5) 低 nibble 序列（32 字节 → 只看低 nibble 是否非 0）
    lo = bytes((v & 0x0F) for v in bb)
    report("低 nibble 序列(32B)", lo)
