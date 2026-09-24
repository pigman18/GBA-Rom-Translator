# -*- coding: utf-8 -*-
"""穷举列相位 + 行偏移(0..5) + 窗口位置，与全库 BDF 做全组合匹配。"""
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
N = len(encs)

# 库：8 列，行窗口 off..off+10（off 0..5）
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

def win(x0, y0, phase, stride, width):
    v = []
    for y in range(y0, y0 + 11):
        for k in range(width):
            x = x0 + phase + stride * k
            v.append(1 if (x < 240 and blue[y, x]) else 0)
    return np.array(v, np.uint8)

best = []
for stride, phase in ((2, 0), (2, 1), (1, 0)):
    for y0 in range(22, 30):
        for x0 in range(0, 240 - 8 * stride):
            t = win(x0, y0, phase, stride, 8)
            n = int(t.sum())
            if n < 25:                       # 要求足够墨，排除巧合
                continue
            for off in range(6):
                R = REFS[off].astype(np.int16)
                D = np.abs(R - t.astype(np.int16)).sum(axis=1)
                i = int(np.argmin(D))
                if D[i] <= 4:
                    best.append((int(D[i]), x0, y0, stride, phase, off, n, encs[i]))

best.sort()
print("=== d<=4 的匹配（stride,phase,off,x0,y0）===")
seen = set()
for b in best[:60]:
    key = (b[1], b[2], b[3], b[4], b[5])
    if key in seen: continue
    seen.add(key)
    print("d=%d  x0=%3d y0=%2d stride=%d phase=%d off=%d 屏墨=%2d -> U+%04X %s"
          % (b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7], chr(b[7])))
if not best:
    print("(无 d<=4)")
    # 输出各组合的最佳
    b2 = []
    for stride, phase in ((2, 0), (2, 1)):
        for y0 in range(22, 30):
            for x0 in range(0, 240 - 8 * stride):
                t = win(x0, y0, phase, stride, 8)
                n = int(t.sum())
                if n < 25: continue
                for off in range(6):
                    R = REFS[off].astype(np.int16)
                    D = np.abs(R - t.astype(np.int16)).sum(axis=1)
                    i = int(np.argmin(D))
                    b2.append((int(D[i]), x0, y0, stride, phase, off, n, encs[i]))
    b2.sort()
    for b in b2[:20]:
        print("d=%d  x0=%3d y0=%2d stride=%d phase=%d off=%d 屏墨=%2d -> U+%04X %s"
              % (b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7], chr(b[7])))
