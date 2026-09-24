# -*- coding: utf-8 -*-
"""foot.py — 统计 VRAM 每个 0x4000 块里「非零 tile」的索引分布（定位引擎预取footprint）。"""
import sys
from pathlib import Path
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")

for tag in sys.argv[1:]:
    v = (T / ("drive_%s_vram.bin" % tag)).read_bytes()
    print("=== %s ===" % tag)
    for blk in range(6):
        base = blk * 0x4000
        if base + 0x4000 > len(v):
            break
        nz = []
        for t in range(512):
            o = base + t * 32
            if any(v[o:o+32]):
                nz.append(t)
        if not nz:
            print("  cb%d @%05X : 全零" % (blk, 0x06000000 + base))
            continue
        # 连续段
        runs, s, p = [], nz[0], nz[0]
        for x in nz[1:]:
            if x == p + 1:
                p = x
            else:
                runs.append((s, p)); s = p = x
        runs.append((s, p))
        rs = " ".join(("%d-%d" % r) if r[0] != r[1] else ("%d" % r[0]) for r in runs)
        print("  cb%d @%05X : nz=%3d  max=%3d  段: %s" % (blk, 0x06000000 + base, len(nz), nz[-1], rs))
