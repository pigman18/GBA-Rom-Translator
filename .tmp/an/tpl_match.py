# -*- coding: utf-8 -*-
"""模板匹配：屏幕上的 8x16 图案到底是不是某个 BDF 字（允许 x/y 偏移）。"""
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
GL = {}
for enc, (bb, bm) in D.items():
    rows = np.zeros((16, 8), dtype=np.int8)
    for r in range(min(16, len(bm))):
        v = int(bm[r], 16)
        for c in range(8):
            rows[r, c] = 1 if (v >> (bb[0] - 1 - c)) & 1 else 0
    GL[enc] = rows

keys = list(GL)
G = np.stack([GL[k] for k in keys])           # (N,16,8)

def match_at(y0, x0, dy_range=(-3, 4), dx_range=(-2, 3)):
    best = []
    for dy in range(*dy_range):
        yy = y0 + dy
        if yy < 0 or yy + 16 > 160:
            continue
        for dx in range(*dx_range):
            xx = x0 + dx
            if xx < 0 or xx + 8 > 240:
                continue
            win = SCR[yy:yy + 16, xx:xx + 8]
            n = win.sum()
            if n == 0:
                continue
            eq = (win[None, :, :] == G).sum(axis=(1, 2))
            sc = eq - 0.35 * np.abs(G.sum(axis=(1, 2)) - n)   # 惩罚墨量不符
            i = int(np.argmax(sc))
            best.append((int(eq[i]), sc[i], keys[i], dy, dx, n, int(G[i].sum())))
    best.sort(key=lambda t: -t[1])
    return best[:4]

# band1 的 3 个中文块，band2 的块
for (y0, x0, tag) in [(26, 16, "band1#1"), (26, 72, "band1#2"), (26, 128, "band1#3"),
                      (42, 16, "band2#1"), (42, 128, "band2#2")]:
    print("\n===== %s  (screen y=%d x=%d) =====" % (tag, y0, x0))
    print("  screen pattern:")
    for r in range(11):
        print("    " + "".join("#" if SCR[y0 + r, x0 + c] else "." for c in range(8)))
    for (eq, sc, enc, dy, dx, n, gn) in match_at(y0, x0):
        ch = chr(enc) if 32 <= enc < 0x110000 else "?"
        print("  -> U+%04X '%s' eq=%d/%d ink(scr=%d,glyph=%d) dy=%d dx=%d" %
              (enc, ch, eq, n, n, gn, dy, dx))
