# -*- coding: utf-8 -*-
"""vdiff.py <tagA> <tagB> — 逐 charBlock 字节差异统计 + 差异落在哪些 tile"""
import sys
from pathlib import Path
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
a = (T / ("drive_%s_vram.bin" % sys.argv[1])).read_bytes()
b = (T / ("drive_%s_vram.bin" % sys.argv[2])).read_bytes()
for cb in range(4):
    off = cb * 0x4000
    da, db = a[off:off + 0x4000], b[off:off + 0x4000]
    dt = [t for t in range(512) if da[t * 32:t * 32 + 32] != db[t * 32:t * 32 + 32]]
    print("cb%d  0x%08X  差异 tile=%3d  %s" % (cb, 0x06000000 + off, len(dt),
          (str(dt[:40]) + ("..." if len(dt) > 40 else "")) if dt else ""))
