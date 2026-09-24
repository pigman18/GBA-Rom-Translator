# -*- coding: utf-8 -*-
"""把屏幕 tile 的"低 nibble"抽成 bit 流（32bit = 4 字节 / 64bit = 8 字节），在 ROM 里定位来源。"""
import numpy as np
from pathlib import Path

ROOT = Path(r"C:\code\GBA-Rom-Translator")
rom = np.fromfile(ROOT / "roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba", dtype=np.uint8)
rb = rom.tobytes(); BASE = 0x08000000

a = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\shot_native.npy").astype(int)
blue = (np.abs(a - np.array([33, 132, 255])).sum(axis=2) < 60)

def occ(pat, limit=10):
    out = []; st = 0
    while len(out) < limit:
        k = rb.find(pat, st)
        if k < 0: break
        out.append(k + BASE); st = k + 1
    return out

def report(name, pat):
    o = occ(pat)
    print("  %-40s %s  -> %d 处 %s" % (name, pat.hex(), len(o), [hex(x) for x in o[:6]]))

print("=" * 96)
for tag, x0, y0 in (("t(x16,y24)", 16, 24), ("t(x24,y24)", 24, 24), ("t(x72,y24)", 72, 24),
                    ("t(x128,y24)", 128, 24), ("t(x128,y32)", 128, 32)):
    print("\n### %s ###" % tag)
    for r in range(8):
        row = "".join("#" if blue[y0 + r, x0 + c] else "." for c in range(8))
        print("    " + row)
    # 低 nibble bit（bit = 低nibble是否非0），每行 4 bit -> 行内 4 位，8 行 = 32 bit = 4 字节
    bits = []
    for r in range(8):
        for c in range(0, 8, 2):
            bits.append(1 if blue[y0 + r, x0 + c] else 0)
    b4 = bytearray()
    for i in range(0, 32, 8):
        v = 0
        for k in range(8):
            v = (v << 1) | bits[i + k]
        b4.append(v)
    report("低nibble bit流 32bit(MSB first)", bytes(b4))
    # 每行 4 bit 放在字节高 4 位
    b4b = bytearray()
    for r in range(8):
        v = 0
        for c in range(0, 8, 2):
            v = (v << 1) | (1 if blue[y0 + r, x0 + c] else 0)
        b4b.append(v << 4)
    report("每行4bit放高4位", bytes(b4b))
    # 每行 4 bit 放低 4 位
    b4c = bytearray(v >> 4 for v in b4b)
    report("每行4bit放低4位", bytes(b4c))
    # 完整 8 列 bit（含奇数列）
    bits8 = []
    for r in range(8):
        for c in range(8):
            bits8.append(1 if blue[y0 + r, x0 + c] else 0)
    b8 = bytearray()
    for i in range(0, 64, 8):
        v = 0
        for k in range(8):
            v = (v << 1) | bits8[i + k]
        b8.append(v)
    report("全8列 bit流 8B", bytes(b8))
