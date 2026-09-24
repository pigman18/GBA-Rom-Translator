# -*- coding: utf-8 -*-
"""slabdump.py <tag> [dom] — 打印 CHS 槽表（ADDR_CHS_SLAB=0x0203E000）。
lo 解码：phase=lo&7, key=lo>>3, ink=key&0xF, lib=(key>>4)&0x3F, code=key>>8。
"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag = sys.argv[1]
doms = [int(sys.argv[2])] if len(sys.argv) > 2 else [0, 1]

KEYS0, STAMPS0 = 0x08, 0x2E8
KEYS1, STAMPS1 = 0x458, 0x738
STRIDE = 4
OWN_BASE, OWN_N = 352, 40
FAR_BASE, FAR_N = 528, 92

ew = (T / ("drive_%s_ewram.bin" % tag)).read_bytes()
SLAB = 0x3E000


def u32(off):
    return struct.unpack_from("<I", ew, SLAB + off)[0]


print("magic=%08X tick=%u" % (u32(0), u32(4)))
for dom in doms:
    ko, so, n, base = (KEYS1, STAMPS1, FAR_N, FAR_BASE) if dom \
        else (KEYS0, STAMPS0, OWN_N, OWN_BASE)
    print("---- dom %d  (keys@%03X stamps@%03X n=%d) ----" % (dom, ko, so, n))
    for i in range(n):
        lo, hi = struct.unpack_from("<II", ew, SLAB + ko + i * 8)
        st = u32(so + i * STRIDE)
        if lo == 0:
            continue
        key = lo >> 3
        phase = lo & 7
        ink = key & 0xF
        lib = (key >> 4) & 0x3F
        code = key >> 8
        if hi:
            hkey = hi >> 3
            hcode, hink, hlib = hkey >> 8, hkey & 0xF, (hkey >> 4) & 0x3F
            hs = "hi=code%04X/l%d/ink%d" % (hcode, hlib, hink)
        else:
            hs = "hi=0"
        print("  slot%-3d tile=%-4d st=%-3d code=%04X lib=%d ink=%2d phase=%d  %s"
              % (i, base + i * STRIDE, st, code, lib, ink, phase, hs))
