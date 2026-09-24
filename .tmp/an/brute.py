# -*- coding: utf-8 -*-
"""穷举：屏幕块 = 某个 BDF 字 经【某种数学变换】得到？（找 100% 匹配）"""
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
        if line.startswith("STARTCHAR"): enc, bb, bm = None, None, []
        elif line.startswith("ENCODING"): enc = int(line.split()[1])
        elif line.startswith("BBX"): bb = [int(v) for v in line.split()[1:4]]
        elif line.startswith("BITMAP"): st = 1
        elif line.startswith("ENDCHAR"):
            if enc is not None: d[enc] = (bb, bm[:])
            st = 0
        elif st: bm.append(line)
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
G = np.stack(G)          # (N,16,8)

def transform(Gl, name):
    """Gl: (N,16,8) -> (N,16,8)"""
    N = Gl.shape[0]
    out = np.zeros_like(Gl)
    if name == "id":
        return Gl
    if name == "dup":       # t[j] = s[j//2]
        for j in range(8): out[:, :, j] = Gl[:, :, j // 2]
    elif name == "take":    # t[j] = s[2j]
        for j in range(8): out[:, :, j] = Gl[:, :, min(7, j * 2)]
    elif name == "take_odd":  # t[j] = s[2j+1]
        for j in range(8): out[:, :, j] = Gl[:, :, min(7, j * 2 + 1)]
    elif name == "mirror":
        out = Gl[:, :, ::-1]
    elif name == "dup+mirror":
        for j in range(8): out[:, :, j] = Gl[:, :, (7 - j) // 2]
    elif name == "shift1":
        out[:, :, 1:] = Gl[:, :, :-1]
    elif name == "shift2":
        out[:, :, :-1] = Gl[:, :, 1:]
    return out

TR = ["id", "dup", "take", "take_odd", "mirror", "dup+mirror", "shift1", "shift2"]

# 屏幕块：band1 的 6 个 8px 位 + band2 的 4 个
BLOCKS = []
for x in (16, 24, 72, 80, 128, 136):
    BLOCKS.append(("band1", 26, x))
for x in (16, 24, 128, 136):
    BLOCKS.append(("band2", 42, x))

print("screen block -> best match (100% would mean a perfect transform)\n")
for (band, y0, x0) in BLOCKS:
    w = SCR[y0:y0 + 16, x0:x0 + 8]
    if w.sum() == 0:
        continue
    best = (0, None, None)
    for tname in TR:
        T = transform(G, tname)
        eq = (w[None] == T).sum(axis=(1, 2))
        i = int(np.argmax(eq))
        if eq[i] > best[0]:
            best = (int(eq[i]), tname, (keys[i], int(T[i].sum())))
    eq, tname, (enc, gn) = best
    print("  %s y=%d x=%d ink=%2d -> %-12s U+%04X '%s' eq=%d/128 (%.1f%%) glyph_ink=%d"
          % (band, y0, x0, w.sum(), tname, enc,
             chr(enc) if 32 <= enc < 0x110000 else "?", eq, eq / 1.28, gn))
