# -*- coding: utf-8 -*-
"""BDF 原始位图 vs 屏幕图案 三方对比。"""
import re, os
import numpy as np

BDF = r"C:\code\GBA-Rom-Translator\fonts\default\Middle.bdf"
OUT = r"C:\code\GBA-Rom-Translator\.tmp\an"

def parse_bdf(path):
    d = {}
    cur = None
    enc = None
    bb = None
    bm = []
    st = 0
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if line.startswith("STARTCHAR"):
            cur, enc, bb, bm = line[10:], None, None, []
        elif line.startswith("ENCODING"):
            enc = int(line.split()[1])
        elif line.startswith("BBX"):
            bb = [int(v) for v in line.split()[1:4]]
        elif line.startswith("BITMAP"):
            st = 1
        elif line.startswith("ENDCHAR"):
            if enc is not None:
                d[enc] = (cur, bb, bm[:])
            st = 0
        elif st:
            bm.append(line)
    return d

D = parse_bdf(BDF)
print("BDF glyphs:", len(D))

# 找包含指定汉字的 STARTCHAR（uniXXXX 名字）
def find(ch):
    u = ord(ch)
    return D.get(u)

def show(bitmap, bb, label, cols=16):
    print("\n--- %s  BBX=%s  rows=%d ---" % (label, bb, len(bitmap)))
    for i, hx in enumerate(bitmap):
        v = int(hx, 16)
        s = "".join("#" if (v >> (bb[0] - 1 - c)) & 1 else "." for c in range(bb[0]))
        print("  %2d %s" % (i, s))

for ch in "只图鉴时间领航":
    r = find(ch)
    if not r:
        print("\n%s: NOT FOUND (U+%04X)" % (ch, ord(ch)))
        continue
    name, bb, bm = r
    show(bm, bb, "%s (%s U+%04X)" % (ch, name, ord(ch)))
