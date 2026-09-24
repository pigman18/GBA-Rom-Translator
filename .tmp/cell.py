# -*- coding: utf-8 -*-
"""cell.py <A我们> <B原盘> <bgNo> — BG 层逐格对照：我们抢的格 / 我们改坏的引擎格"""
import re, struct, sys
from pathlib import Path
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
def io(tag):
    txt = (T / ("drive_%s.log" % tag)).read_text(encoding="utf-8", errors="replace")
    return {m.group(1): int(m.group(2), 16)
            for m in re.finditer(r"IO (\w+) 0x[0-9a-f]+:\s*(0x[0-9a-fA-F]+)", txt)}
def load(tag, n):
    v = (T / ("drive_%s_vram.bin" % tag)).read_bytes()
    c = io(tag).get("BG%dCNT" % n, 0)
    return v, ((c >> 2) & 3) * 0x4000, ((c >> 8) & 0x1F) * 0x800
A, B, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
va, cba, sba = load(A, n); vb, cbb, sbb = load(B, n)
def cell(v, sb, ty, tx): return struct.unpack_from("<H", v, sb + (ty*32+tx)*2)[0] & 0x3FF
print("== 我们抢的格（B 有内容、A 换成别的号）==")
taken = []
for ty in range(20):
    for tx in range(30):
        a, b = cell(va, sba, ty, tx), cell(vb, sbb, ty, tx)
        if a != b:
            taken.append((ty, tx, b, a))
for ty, tx, b, a in taken:
    same = "同内容" if va[cba+a*32:cba+a*32+32] == vb[cbb+b*32:cbb+b*32+32] else ""
    print("  r%02d c%02d  %4d -> %4d  (原 tile nz=%2d, 现 tile nz=%2d) %s"
          % (ty, tx, b, a, sum(1 for x in vb[cbb+b*32:cbb+b*32+32] if x), sum(1 for x in va[cba+a*32:cba+a*32+32] if x), same))
print("  共 %d 格" % len(taken))
print("== 我们改坏的「原盘仍引用」号 ==")
ref = set()
for ty in range(20):
    for tx in range(30):
        t = cell(vb, sbb, ty, tx)
        if t: ref.add(t)
bad = [t for t in sorted(ref) if va[cba+t*32:cba+t*32+32] != vb[cbb+t*32:cbb+t*32+32]]
for t in bad:
    cells = [(ty,tx) for ty in range(20) for tx in range(30) if cell(vb,sbb,ty,tx)==t]
    na = sum(1 for x in va[cba+t*32:cba+t*32+32] if x); nb = sum(1 for x in vb[cbb+t*32:cbb+t*32+32] if x)
    print("  号 %3d  原盘格 %s  原 nz=%d → 现 nz=%d" % (t, cells, nb, na))
