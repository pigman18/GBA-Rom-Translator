# -*- coding: utf-8 -*-
"""逐像素滑窗：把屏幕的 8x11 与全库字形（BDF 行2..12）比对，找最小距离点并打印对照。"""
import re, numpy as np
from pathlib import Path

ROOT = Path(r"C:\code\GBA-Rom-Translator")
text = (ROOT / "fonts/default/Middle.bdf").read_text("utf-8", errors="replace")
GB = {}
for m in re.finditer(r"^STARTCHAR.*?^ENCODING\s+(\d+).*?^BITMAP\s*$(.*?)^ENDCHAR",
                     text, re.M | re.S):
    enc = int(m.group(1))
    GB[enc] = [int(l.strip(), 16) for l in m.group(2).strip().splitlines() if l.strip()]
encs = sorted(GB)

REF = np.zeros((len(encs), 88), np.uint8)
for i, e in enumerate(encs):
    r = GB[e]; v = []
    for y in range(2, 13):
        H = (r[y] >> 8) & 0xFF if y < len(r) else 0
        for x in range(8):
            v.append((H >> (7 - x)) & 1)
    REF[i] = v
RS = REF.sum(axis=1).astype(np.int16)

a = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\shot_native.npy").astype(int)
INK = np.array([33, 132, 255]); WHT = np.array([255, 255, 255])
ink = (np.abs(a - INK).sum(axis=2) < np.abs(a - WHT).sum(axis=2))

# 只看文本行所在的带
Y0CAND = [22, 24, 26]
res = []
for y0 in Y0CAND:
    for x0 in range(0, 233):
        t = ink[y0:y0 + 11, x0:x0 + 8].astype(np.int16).reshape(-1)
        n = int(t.sum())
        if n < 18:
            continue
        D = np.abs(REF.astype(np.int16) - t).sum(axis=1)
        i = int(np.argmin(D))
        res.append((int(D[i]), x0, y0, n, encs[i]))

res.sort()
print("=== 滑窗最佳 25 个 ===")
for r in res[:25]:
    print("d=%3d x0=%3d y0=%2d 屏墨=%2d -> U+%04X %s (库墨 %d)"
          % (r[0], r[1], r[2], r[3], r[4], chr(r[4]), RS[encs.index(r[4])]))

# 打印最佳点的 ASCII 对照
def show(x0, y0, enc):
    t = ink[y0:y0 + 11, x0:x0 + 8]
    r = GB[enc]
    print("\n屏幕 x0=%d y0=%d   |   库字 U+%04X %s" % (x0, y0, enc, chr(enc)))
    print("    屏 8x11       库 8x11(行2..12)")
    for k in range(11):
        s1 = "".join("#" if t[k, x] else "." for x in range(8))
        H = (r[2 + k] >> 8) & 0xFF
        s2 = "".join("#" if (H >> (7 - x)) & 1 else "." for x in range(8))
        print("  %2d %s   %s" % (k, s1, s2))

for r in res[:4]:
    show(r[1], r[2], r[4])
