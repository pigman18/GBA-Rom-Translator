# -*- coding: utf-8 -*-
"""认出屏幕上的字：对截图文本带做多种采样假设，与全库 BDF 字形匹配。"""
import re, numpy as np
from pathlib import Path

ROOT = Path(r"C:\code\GBA-Rom-Translator")
BDF = ROOT / "fonts/default/Middle.bdf"

text = BDF.read_text("utf-8", errors="replace")
GB = {}
for m in re.finditer(r"^STARTCHAR.*?^ENCODING\s+(\d+).*?^BITMAP\s*$(.*?)^ENDCHAR",
                     text, re.M | re.S):
    enc = int(m.group(1))
    rows = [int(l.strip(), 16) for l in m.group(2).strip().splitlines() if l.strip()]
    GB[enc] = rows
print("BDF 字数", len(GB))

# 索引：把每个字的 8x11（行 2..12，列 0..7）打成 88 bit 向量
encs = sorted(GB)
REF = np.zeros((len(encs), 88), np.uint8)
for i, e in enumerate(encs):
    r = GB[e]
    v = []
    for y in range(2, 13):
        H = (r[y] >> 8) & 0xFF if y < len(r) else 0
        for x in range(8):
            v.append((H >> (7 - x)) & 1)
    REF[i] = v
print("参考矩阵", REF.shape)

a = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\shot_native.npy").astype(int)
INK = np.array([33, 132, 255]); WHT = np.array([255, 255, 255])
d_ink = np.abs(a - INK).sum(axis=2)
d_wht = np.abs(a - WHT).sum(axis=2)
ink = d_ink < d_wht          # 更接近墨色

def sample(x0, y0, kind):
    """从 ink 取 8 列 x 11 行的采样。kind: 'id' 连续 / 'even' 偶列 / 'odd' 奇列。"""
    v = []
    for y in range(y0, y0 + 11):
        for k in range(8):
            if kind == "id":
                x = x0 + k
            elif kind == "even":
                x = x0 + 2 * k
            else:
                x = x0 + 1 + 2 * k
            v.append(1 if (0 <= y < 160 and 0 <= x < 240 and ink[y, x]) else 0)
    return np.array(v, np.uint8)

best = []
for y0 in (24, 22, 26, 20):
    for x0 in range(0, 224, 8):
        for kind in ("id", "even", "odd"):
            t = sample(x0, y0, kind)
            if t.sum() < 15:
                continue
            D = np.abs(REF.astype(np.int16) - t.astype(np.int16)).sum(axis=1)
            i = int(np.argmin(D))
            best.append((int(D[i]), x0, y0, kind, int(t.sum()), encs[i], int(REF[i].sum())))

best.sort()
print("\n=== 最佳 20 个 (d, x0, y0, kind, 屏墨, 命中字, 库墨) ===")
for b in best[:20]:
    ch = chr(b[5])
    print("d=%3d  x0=%3d y0=%2d %-5s 屏墨=%2d  ->  U+%04X %s (库墨 %d)"
          % (b[0], b[1], b[2], b[3], b[4], b[5], ch, b[6]))

print("\n=== 只保留 d<=12 的 ===")
for b in [x for x in best if x[0] <= 12][:20]:
    print("d=%3d  x0=%3d y0=%2d %-5s 屏墨=%2d  ->  U+%04X %s"
          % (b[0], b[1], b[2], b[3], b[4], b[5], chr(b[5])))
