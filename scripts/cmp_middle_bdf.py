"""逐字模对比：HEAD 版 vs 工作区版 Middle.bdf

用法：
    python scripts/cmp_middle_bdf.py 36947 21495 36335
（默认对比 道 号 路）

输出每个字两个 16x16 点阵并排，并给出：
  · 墨迹 bbox（min/max 行列）
  · 互不相同的位数
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BDF = "fonts/default/Middle.bdf"


def load_bdf(text):
    """→ {codepoint: (w, h, xoff, yoff, [row_ints])}"""
    out = {}
    cp = None
    rows = []
    w = h = xo = yo = None
    bitmaps = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("ENCODING "):
            cp = int(line.split()[1])
        elif line.startswith("BBX "):
            p = line.split()
            w, h, xo, yo = int(p[1]), int(p[2]), int(p[3]), int(p[4])
        elif line.startswith("BITMAP"):
            bitmaps = True
            rows = []
        elif line.startswith("ENDCHAR"):
            if cp is not None and rows:
                out[cp] = (w, h, xo, yo, rows)
            bitmaps = False
            cp = None
        elif bitmaps:
            try:
                rows.append(int(line, 16))
            except ValueError:
                pass
    return out


def ink_bbox(g):
    w, h, xo, yo, rows = g
    xs, ys = [], []
    for r, v in enumerate(rows):
        for c in range(w):
            if (v >> (w - 1 - c)) & 1:
                xs.append(c)
                ys.append(r)
    if not xs:
        return None
    return min(xs), max(xs), min(ys), max(ys)


def show(g, title):
    w, h, xo, yo, rows = g
    print("  %s  BBX %dx%d%+d%+d  rows=%d  bbox=%s" %
          (title, w, h, xo, yo, len(rows), ink_bbox(g)))
    for v in rows:
        print("    " + "".join('#' if (v >> (w - 1 - c)) & 1 else '.'
                               for c in range(w)))


def main():
    cps = [int(a, 0) for a in sys.argv[1:]] or [0x9053, 0x53F7, 0x8DEF]
    head = subprocess.run(["git", "show", "HEAD:" + BDF], cwd=ROOT,
                          capture_output=True, check=True).stdout.decode("utf-8", "replace")
    work = (ROOT / BDF).read_text(encoding="utf-8", errors="replace")
    H, W = load_bdf(head), load_bdf(work)
    print("HEAD 字形数=%d   工作区字形数=%d" % (len(H), len(W)))
    for cp in cps:
        ch = chr(cp)
        print("\n" + "=" * 60)
        print("ENCODING %d  U+%04X  '%s'" % (cp, cp, ch))
        if cp not in H or cp not in W:
            print("  缺失: HEAD=%s 工作区=%s" % (cp in H, cp in W))
            continue
        show(H[cp], "HEAD  ")
        show(W[cp], "WORK  ")
        gh, gw = H[cp], W[cp]
        if gh[0] == gw[0] and len(gh[4]) == len(gw[4]):
            diff = sum(bin(a ^ b).count("1") for a, b in zip(gh[4], gw[4]))
            print("  差异位数 = %d" % diff)
        else:
            print("  几何不同：HEAD %dx%d rows=%d / WORK %dx%d rows=%d" %
                  (gh[0], gh[1], len(gh[4]), gw[0], gw[1], len(gw[4])))


if __name__ == "__main__":
    raise SystemExit(main())
