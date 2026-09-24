# -*- coding: utf-8 -*-
"""穷举：把库字形按各种"展开成 16px"方式生成模板，与屏幕全位置滑窗匹配（墨量预筛）。"""
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
print("库字数", N)

# base：8 列 x 11 行
B = np.zeros((N, 11, 8), np.uint8)
for i, e in enumerate(encs):
    r = GB[e]
    for y in range(11):
        H = (r[2 + y] >> 8) & 0xFF if 2 + y < len(r) else 0
        for x in range(8):
            B[i, y, x] = (H >> (7 - x)) & 1
BN = B.reshape(N, -1).sum(axis=1).astype(np.int16)

def expand(kind):
    """8 列 -> 16 列"""
    if kind == "spread":            # 列 i -> 2i，间隙 0
        T = np.zeros((N, 11, 16), np.uint8); T[:, :, 0::2] = B
    elif kind == "spread_o":        # 列 i -> 2i+1
        T = np.zeros((N, 11, 16), np.uint8); T[:, :, 1::2] = B
    elif kind == "dup":             # 列 i -> 2i,2i+1
        T = np.repeat(B, 2, axis=2)
    elif kind == "half":            # 只取左 8 列（本身就是 8 列）+ 右侧留空
        T = np.zeros((N, 11, 16), np.uint8); T[:, :, 0:8] = B
    elif kind == "mirror_pair":     # 左 = 原字，右 = 镜像
        T = np.zeros((N, 11, 16), np.uint8); T[:, :, 0:8] = B; T[:, :, 8:16] = B[:, :, ::-1]
    elif kind == "dup_pair":        # 左 = 原字，右 = 原字
        T = np.zeros((N, 11, 16), np.uint8); T[:, :, 0:8] = B; T[:, :, 8:16] = B
    return T.reshape(N, -1)

a = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\shot_native.npy").astype(int)
blue = (np.abs(a - np.array([33, 132, 255])).sum(axis=2) < 60)

wins = []
for y0 in range(22, 30):
    for x0 in range(0, 225):
        w = blue[y0:y0 + 11, x0:x0 + 16].reshape(-1).astype(np.int16)
        n = int(w.sum())
        if n >= 12:
            wins.append((x0, y0, n, w))
print("候选窗口", len(wins))

best_all = []
for kind in ("spread", "spread_o", "dup", "half", "mirror_pair", "dup_pair"):
    T = expand(kind).astype(np.int16)
    TN = T.sum(axis=1)
    best = (10**9, None)
    for x0, y0, n, w in wins:
        cand = np.nonzero(np.abs(TN - n) <= 8)[0]
        if len(cand) == 0: continue
        D = np.abs(T[cand] - w).sum(axis=1)
        k = int(np.argmin(D))
        if D[k] < best[0]:
            best = (int(D[k]), (x0, y0, n, encs[cand[k]]))
    print("  %-12s best d=%3d  @%s" % (kind, best[0], best[1] and
          "x0=%d y0=%d 屏墨=%d -> U+%04X %s" % (best[1][0], best[1][1], best[1][2],
                                                best[1][3], chr(best[1][3]))))
    best_all.append((best[0], kind, best[1]))

best_all.sort()
print("\n=== 总排名 ===")
for d, k, info in best_all:
    print("  %-12s d=%3d  %s" % (k, d, info and "x0=%d y0=%d -> U+%04X %s"
          % (info[0], info[1], info[3], chr(info[3]))))
