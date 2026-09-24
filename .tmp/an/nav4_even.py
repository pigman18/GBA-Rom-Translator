# -*- coding: utf-8 -*-
"""偶数列采样滑窗：假设屏幕字形只有偶数列有效，与全库 BDF 做全位置匹配。"""
import re, numpy as np
from pathlib import Path

ROOT = Path(r"C:\code\GBA-Rom-Translator")
text = (ROOT / "fonts/default/Middle.bdf").read_text("utf-8", errors="replace")
GB = {}
for m in re.finditer(r"^STARTCHAR.*?^ENCODING\s+(\d+).*?^BITMAP\s*$(.*?)^ENDCHAR",
                     text, re.M | re.S):
    GB[int(m.group(1))] = [int(l.strip(), 16) for l in
                           m.group(2).strip().splitlines() if l.strip()]
encs = sorted(GB)
REF = np.zeros((len(encs), 88), np.uint8)
for i, e in enumerate(encs):
    r = GB[e]; v = []
    for y in range(2, 13):
        H = (r[y] >> 8) & 0xFF if y < len(r) else 0
        for x in range(8):
            v.append((H >> (7 - x)) & 1)
    REF[i] = v

a = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\shot_native.npy").astype(int)
blue = (np.abs(a - np.array([33, 132, 255])).sum(axis=2) < 60)

res = []
for y0 in range(22, 29):
    for x0 in range(0, 225):
        v = []
        for y in range(y0, y0 + 11):
            for k in range(8):
                x = x0 + 2 * k
                v.append(1 if (x < 240 and blue[y, x]) else 0)
        t = np.array(v, np.uint8)
        if t.sum() < 14: continue
        D = np.abs(REF.astype(np.int16) - t.astype(np.int16)).sum(axis=1)
        i = int(np.argmin(D))
        res.append((int(D[i]), x0, y0, int(t.sum()), encs[i]))

res.sort()
print("=== 偶数列采样滑窗 最佳 25 ===")
for r in res[:25]:
    print("d=%3d x0=%3d y0=%2d 屏墨=%2d -> U+%04X %s" % (r[0], r[1], r[2], r[3], r[4], chr(r[4])))

print("\n=== d<=6 全部 ===")
for r in [x for x in res if x[0] <= 6]:
    print("d=%3d x0=%3d y0=%2d 屏墨=%2d -> U+%04X %s" % (r[0], r[1], r[2], r[3], r[4], chr(r[4])))

# 打印最佳点的对照
def show(x0, y0, enc):
    r = GB[enc]
    print("\n屏幕 even x0=%d y0=%d  vs  库 U+%04X %s" % (x0, y0, enc, chr(enc)))
    for k in range(11):
        y = y0 + k
        s1 = "".join("#" if blue[y, x0 + 2 * i] else "." for i in range(8))
        H = (r[2 + k] >> 8) & 0xFF
        s2 = "".join("#" if (H >> (7 - x)) & 1 else "." for x in range(8))
        print("  %s  |  %s" % (s1, s2))

for r in res[:3]:
    show(r[1], r[2], r[4])
