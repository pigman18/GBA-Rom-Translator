# -*- coding: utf-8 -*-
"""子集判定：屏幕墨迹 S 是否包含某个 BDF 字 A（A 的墨像素全在 S 上）？
若是 => S = A OR (别的数据)，即两套写方叠加。纯数学，O(N*128)。"""
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
G = np.stack(G)

BLOCKS = []
for x in (16, 24, 72, 80, 128, 136):
    BLOCKS.append(("band1", 26, x))
for x in (16, 24, 128, 136):
    BLOCKS.append(("band2", 42, x))

print("subset search: A ⊆ S  (A.ink 像素全落在 S 的墨上)\n")
for (band, y0, x0) in BLOCKS:
    S = SCR[y0:y0 + 16, x0:x0 + 8]
    if S.sum() == 0:
        continue
    # 只在墨迹行范围内比较（允许垂直 ±3 偏移）
    best = []
    for dy in (-3, -2, -1, 0, 1, 2, 3):
        yy = y0 + dy
        if yy < 0 or yy + 16 > 160:
            continue
        W = SCR[yy:yy + 16, x0:x0 + 8]
        miss = (G & (1 - W[None])).sum(axis=(1, 2))   # A 有墨而 S 无 的像素数
        ink = G.sum(axis=(1, 2))
        ok = miss == 0
        for i in np.nonzero(ok)[0]:
            best.append((int(ink[i]), keys[i], dy))
    best.sort(key=lambda t: -t[0])
    print("=== %s y=%d x=%d  S.ink=%d ===" % (band, y0, x0, S.sum()))
    if not best:
        print("    无完全子集字")
    else:
        for (ink, enc, dy) in best[:6]:
            ch = chr(enc) if 32 <= enc < 0x110000 else "?"
            print("    ⊇ U+%04X '%s' ink=%2d dy=%d  (覆盖 %.0f%%)"
                  % (enc, ch, ink, dy, 100.0 * ink / max(1, int(S.sum()))))
