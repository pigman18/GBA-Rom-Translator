# -*- coding: utf-8 -*-
"""视觉对照：屏幕图案(各种采样) vs 全库最佳候选字形，放大并排输出 PNG。"""
import re, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(r"C:\code\GBA-Rom-Translator")
text = (ROOT / "fonts/default/Middle.bdf").read_text("utf-8", errors="replace")
GB = {}
for m in re.finditer(r"^STARTCHAR.*?^ENCODING\s+(\d+).*?^BITMAP\s*$(.*?)^ENDCHAR",
                     text, re.M | re.S):
    GB[int(m.group(1))] = [int(l.strip(), 16) for l in
                           m.group(2).strip().splitlines() if l.strip()]
encs = sorted(GB); N = len(encs)

# 库：允许行偏移 0..5，做成 (off,N,88)
REFS = {}
for off in range(6):
    R = np.zeros((N, 88), np.uint8)
    for i, e in enumerate(encs):
        r = GB[e]; v = []
        for y in range(off, off + 11):
            H = (r[y] >> 8) & 0xFF if y < len(r) else 0
            for x in range(8):
                v.append((H >> (7 - x)) & 1)
        R[i] = v
    REFS[off] = R

a = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\shot_native.npy").astype(int)
blue = (np.abs(a - np.array([33, 132, 255])).sum(axis=2) < 60)

def sample(x0, y0, stride, phase, width=8, rows=11):
    v = []
    for y in range(y0, y0 + rows):
        for k in range(width):
            x = x0 + phase + stride * k
            v.append(1 if (x < 240 and blue[y, x]) else 0)
    return np.array(v, np.uint8)

def best_for(x0, y0, stride, phase):
    t = sample(x0, y0, stride, phase)
    if t.sum() < 18: return None
    bb = (10**9, None, None)
    for off in range(6):
        D = np.abs(REFS[off].astype(np.int16) - t.astype(np.int16)).sum(axis=1)
        i = int(np.argmin(D))
        if D[i] < bb[0]: bb = (int(D[i]), encs[i], off)
    return (bb[0], bb[1], bb[2], t)

# 候选窗口（有墨的连续区）
CANDS = [(16, 26), (24, 26), (72, 26), (80, 26), (128, 26), (136, 26),
         (16, 42), (24, 42), (80, 42), (88, 42), (128, 42), (136, 42)]
Z = 6
PAD = 30
cells = []
for x0, y0 in CANDS:
    for stride, phase, nm in ((1, 0, "1:1"), (2, 0, "even"), (2, 1, "odd")):
        b = best_for(x0, y0, stride, phase)
        if b: cells.append((x0, y0, nm, b))
print("生成 %d 个对照单元" % len(cells))

CW = 8 * Z + PAD * 2
CH = 11 * Z + 70
COLS = 3
ROWS = (len(cells) + COLS - 1) // COLS
im = Image.new("RGB", (COLS * CW, ROWS * CH), (24, 24, 28))
d = ImageDraw.Draw(im)
for n, (x0, y0, nm, (dist, enc, off, t)) in enumerate(cells):
    cx = (n % COLS) * CW
    cy = (n // COLS) * CH
    d.text((cx + 4, cy + 2), "screen x=%d y=%d [%s]" % (x0, y0, nm), fill=(255, 220, 120))
    d.text((cx + 4, cy + 16), "best d=%d  U+%04X %s  (BDF off=%d)"
           % (dist, enc, chr(enc), off), fill=(160, 255, 180))
    # 屏幕图案
    for y in range(11):
        for k in range(8):
            xx = cx + 20 + k * Z; yy = cy + 34 + y * Z
            d.rectangle([xx, yy, xx + Z - 1, yy + Z - 1],
                        fill=(40, 140, 255) if t[y * 8 + k] else (240, 240, 246))
    # 库字形
    r = GB[enc]
    for y in range(11):
        H = (r[off + y] >> 8) & 0xFF if off + y < len(r) else 0
        for k in range(8):
            xx = cx + 20 + 8 * Z + 24 + k * Z; yy = cy + 34 + y * Z
            on = (H >> (7 - k)) & 1
            d.rectangle([xx, yy, xx + Z - 1, yy + Z - 1],
                        fill=(255, 90, 90) if on else (240, 240, 246))
    d.text((cx + 20, cy + 34 + 11 * Z + 4), "screen", fill=(120, 190, 255))
    d.text((cx + 20 + 8 * Z + 24, cy + 34 + 11 * Z + 4), "library", fill=(255, 140, 140))
out = r"C:\code\GBA-Rom-Translator\.tmp\an\nav4_compare.png"
im.save(out)
print("saved", out, im.size)
