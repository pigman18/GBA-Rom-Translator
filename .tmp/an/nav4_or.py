# -*- coding: utf-8 -*-
"""OR 分解：屏幕图案 = A | B（两字重叠）？—— 检验"槽冲突导致重影"假说。"""
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
B = np.zeros((N, 11, 8), np.uint8)
for i, e in enumerate(encs):
    r = GB[e]
    for y in range(11):
        H = (r[2 + y] >> 8) & 0xFF if 2 + y < len(r) else 0
        for x in range(8):
            B[i, y, x] = (H >> (7 - x)) & 1
BF = B.reshape(N, 88)
BN = BF.sum(axis=1)
print("库字形墨量: min=%d max=%d mean=%.1f" % (BN.min(), BN.max(), BN.mean()))
print("墨量>=40 的字数:", int((BN >= 40).sum()), " >=45:", int((BN >= 45).sum()))

a = np.load(r"C:\code\GBA-Rom-Translator\.tmp\an\shot_native.npy").astype(int)
blue = (np.abs(a - np.array([33, 132, 255])).sum(axis=2) < 60)


def screen_8x11_even(x0, y0):
    v = []
    for y in range(y0, y0 + 11):
        for k in range(8):
            x = x0 + 2 * k
            v.append(1 if (x < 240 and blue[y, x]) else 0)
    return np.array(v, np.uint8)


def screen_8x11_id(x0, y0):
    return blue[y0:y0 + 11, x0:x0 + 8].reshape(-1).astype(np.uint8)


def decompose(P):
    """找 (i,j) 使 BF[i] | BF[j] == P"""
    n = int(P.sum())
    # 要求 A ⊆ P
    okA = ((BF & (1 - P)).sum(axis=1) == 0)
    cand = np.nonzero(okA)[0]
    cand = cand[np.argsort(-BN[cand])]          # 墨多的优先
    sols = []
    for ia in cand[:400]:
        A = BF[ia]
        rem = P & (1 - A)
        if rem.sum() == 0:
            sols.append((int(ia), int(ia), n))
            continue
        # B 必须覆盖 rem 且 ⊆ P
        good = ((BF & (1 - rem)).sum(axis=1) == rem.sum())
        good &= ((BF & (1 - P)).sum(axis=1) == 0)
        js = np.nonzero(good)[0]
        for jb in js[:8]:
            sols.append((int(ia), int(jb), n))
        if len(sols) > 12:
            break
    return sols, len(cand)


targets = [("行1 x16", 16, 26, "even"), ("行1 x72", 72, 26, "even"),
           ("行1 x128", 128, 26, "even"), ("行1 x16", 16, 26, "id"),
           ("行2 x16", 16, 42, "even"), ("行2 x80", 80, 42, "even"),
           ("行2 x128", 128, 42, "even")]
for name, x0, y0, kind in targets:
    P = screen_8x11_even(x0, y0) if kind == "even" else screen_8x11_id(x0, y0)
    n = int(P.sum())
    sols, ncand = decompose(P)
    print("\n--- %s %s(y0=%d) 屏墨=%d  子集候选=%d ---" % (name, kind, y0, n, ncand))
    if not sols:
        print("   ✗ 无法用 (A|B) 分解")
    for ia, jb, nn in sols[:6]:
        print("   A=U+%04X %s | B=U+%04X %s  (墨 %d/%d, 目标 %d)"
              % (encs[ia], chr(encs[ia]), encs[jb], chr(encs[jb]), BN[ia], BN[jb], nn))
    # 打印 P
    print("   屏幕图案:")
    for y in range(11):
        print("     " + "".join("#" if P[y * 8 + x] else "." for x in range(8)))
