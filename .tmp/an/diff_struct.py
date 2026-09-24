# -*- coding: utf-8 -*-
"""差异结构分析：屏幕图案 vs 最佳匹配 BDF 字，画 XOR。"""
import numpy as np
from PIL import Image

BDF = r"C:\code\GBA-Rom-Translator\fonts\default\Middle.bdf"
SHOT = r"C:\Users\Administrator\.workbuddy\clipboard-images\clipboard-2026-09-22T08-34-54-307Z-4d6b3feb.png"

a = np.array(Image.open(SHOT).convert("RGB"))
g = a[54:214, 1:241]
WHITE = np.array([255, 255, 255]); BLUE = np.array([0x21, 0x84, 0xFF])
d_w = np.abs(g.astype(np.int16) - WHITE).sum(axis=2)
d_b = np.abs(g.astype(np.int16) - BLUE).sum(axis=2)
SCR = ((d_b <= 60) & (d_b < d_w)).astype(np.int8)

def parse_bdf(path):
    d, enc, bb, bm, st = {}, None, None, [], 0
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if line.startswith("STARTCHAR"):
            enc, bb, bm = None, None, []
        elif line.startswith("ENCODING"):
            enc = int(line.split()[1])
        elif line.startswith("BBX"):
            bb = [int(v) for v in line.split()[1:4]]
        elif line.startswith("BITMAP"):
            st = 1
        elif line.startswith("ENDCHAR"):
            if enc is not None:
                d[enc] = (bb, bm[:])
            st = 0
        elif st:
            bm.append(line)
    return d

D = parse_bdf(BDF)
G, keys = [], []
for enc, (bb, bm) in D.items():
    rows = np.zeros((16, 8), dtype=np.int8)
    for r in range(min(16, len(bm))):
        v = int(bm[r], 16)
        for c in range(8):
            rows[r, c] = 1 if (v >> (bb[0] - 1 - c)) & 1 else 0
    G.append(rows); keys.append(enc)
G = np.stack(G)

def best(y0, x0):
    b = None
    for dy in range(-4, 5):
        for dx in range(-3, 4):
            yy, xx = y0 + dy, x0 + dx
            if yy < 0 or yy + 16 > 160 or xx < 0 or xx + 8 > 240:
                continue
            w = SCR[yy:yy + 16, xx:xx + 8]
            eq = (w[None] == G).sum(axis=(1, 2))
            i = int(np.argmax(eq))
            if b is None or eq[i] > b[0]:
                b = (int(eq[i]), keys[i], G[i], dy, dx, w)
    return b

for (y0, x0, tag) in [(26, 16, "band1#1"), (26, 72, "band1#2"), (26, 128, "band1#3"),
                      (42, 16, "band2#1"), (42, 128, "band2#2")]:
    eq, enc, gl, dy, dx, w = best(y0, x0)
    print("\n### %s (y=%d x=%d)  best=U+%04X '%s'  eq=%d/128 (%.1f%%)  dy=%d dx=%d"
          % (tag, y0, x0, enc, chr(enc) if 32 <= enc < 0x110000 else "?", eq, eq / 1.28, dy, dx))
    print("    SCREEN            BDF(GLYPH)        XOR")
    for r in range(16):
        s = "".join("#" if w[r, c] else "." for c in range(8))
        gs = "".join("#" if gl[r, c] else "." for c in range(8))
        x = "".join("X" if w[r, c] != gl[r, c] else " " for c in range(8))
        print("    %s  |  %s  |  %s" % (s, gs, x))
