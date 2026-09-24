# -*- coding: utf-8 -*-
"""纯蓝墨滑窗 + 16px 图案压缩成 8 列，肉眼认字。"""
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
blue = (np.abs(a - np.array([33, 132, 255])).sum(axis=2) < 60)   # 严格蓝墨

print("=== 严格蓝墨行的列分布 ===")
for y in range(24, 56):
    cs = np.nonzero(blue[y])[0]
    if len(cs) == 0: continue
    print("%3d: %s" % (y, " ".join(str(c) for c in cs)))

# ---- 滑窗（步进 1），纯蓝墨 ----
print("\n=== 纯蓝墨滑窗最佳 20 ===")
res = []
for y0 in (24, 25, 26):
    for x0 in range(0, 233):
        t = blue[y0:y0 + 11, x0:x0 + 8].astype(np.int16).reshape(-1)
        if t.sum() < 12: continue
        D = np.abs(REF.astype(np.int16) - t).sum(axis=1)
        i = int(np.argmin(D))
        res.append((int(D[i]), x0, y0, int(t.sum()), encs[i]))
res.sort()
for r in res[:20]:
    print("d=%3d x0=%3d y0=%2d 屏墨=%2d -> U+%04X %s" % (r[0], r[1], r[2], r[3], r[4], chr(r[4])))

# ---- 16px 图案 → 8 列压缩 ----
print("\n=== 16px 区域按偶/奇列压成 8 列（肉眼认字） ===")
for tag, xa, ya in (("行1 x16", 16, 26), ("行1 x72", 72, 26), ("行1 x128", 128, 26),
                    ("行2 x16", 16, 42), ("行2 x80", 80, 42), ("行2 x128", 128, 42)):
    print("\n--- %s (y=%d..%d) ---" % (tag, ya, ya + 10))
    print("  原 16 列:              |  偶数列→8:    |  奇数列→8:")
    for k in range(11):
        y = ya + k
        raw = "".join("#" if blue[y, xa + i] else "." for i in range(16))
        ev = "".join("#" if blue[y, xa + 2 * i] else "." for i in range(8))
        od = "".join("#" if blue[y, xa + 2 * i + 1] else "." for i in range(8))
        print("  %s | %s | %s" % (raw, ev, od))
