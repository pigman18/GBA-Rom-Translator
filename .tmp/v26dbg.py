# -*- coding: utf-8 -*-
"""v26dbg.py <tag> <win_hex> <dom> <slot> — 单槽 v26 逐列并排诊断。"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag, win_addr, dom, slot = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3]), int(sys.argv[4])
vram = (T / ("drive_%s_vram.bin" % tag)).read_bytes()
iw = (T / ("drive_%s_iwram.bin" % tag)).read_bytes()
ew = (T / ("drive_%s_ewram.bin" % tag)).read_bytes()
SLAB, STRIDE = 0x3E000, 4
KEYS = {0: 0x08, 1: 0x458}
OWN_BASE, FAR_BASE = 352, 528
SLOT_N = {0: 40, 1: 92}


rom = Path(r"C:/code/GBA-Rom-Translator/roms/outputs/_t1.gba").read_bytes()


def rd8(a):
    return (iw if a >= 0x03000000 else ew)[a - (0x03000000 if a >= 0x03000000 else 0x02000000)]


def rd32(a):
    if a >= 0x08000000:
        return struct.unpack_from("<I", rom, a - 0x08000000)[0]
    buf, base = (iw, 0x03000000) if a >= 0x03000000 else (ew, 0x02000000)
    return struct.unpack_from("<I", buf, a - base)[0]


TPLD = rd32(rd32(win_addr + 0x00) + 0x0C)
TB = rd8(win_addr + 0x16)
VOFF = (TPLD - 0x06000000) & 0x1FFFF
BASE = (FAR_BASE + TB) if dom else OWN_BASE


def tile(n):
    return vram[VOFF + n * 32:VOFF + n * 32 + 32]


def px(t, x, y):
    return (t[y * 4 + (x >> 1)] >> ((x & 1) * 4)) & 0xF


def col(t, x):
    return ''.join('%X' % px(t, x, y) for y in range(8))


lo, hi = struct.unpack_from("<II", ew, SLAB + KEYS[dom] + slot * 8)
ph, code, ink = lo & 7, (lo >> 3) >> 8, (lo >> 3) & 0xF
pj = None
for i in range(SLOT_N[dom]):
    if struct.unpack_from("<I", ew, SLAB + KEYS[dom] + i * 8)[0] == hi:
        pj = i
tl = BASE + slot * STRIDE
pt = (BASE + pj * STRIDE) if pj is not None else None
print("dom%d slot%d tile=%d code=%04X ink=%d phase=%d hi=%08X prevSlot=%s prevTile=%s"
      % (dom, slot, tl, code, ink, ph, hi, pj, pt))
print("--- 本槽 4 砖 ---")
for k, nm in enumerate(("TL", "BL", "TR", "BR")):
    print("  %s(%d)" % (nm, tl + k))
    for y in range(8):
        print("    ", ''.join('%X' % px(tile(tl + k), x, y) for x in range(8)))
if pt is not None:
    print("--- 上一字 4 砖 ---")
    for k, nm in enumerate(("TL", "BL", "TR", "BR")):
        print("  %s(%d)" % (nm, pt + k))
        for y in range(8):
            print("    ", ''.join('%X' % px(tile(pt + k), x, y) for x in range(8)))
    print("--- 逐列 (y=0..7) : 本槽L / 上一字BR ---")
    for x in range(ph):
        print("  col%d dstL=%s  srcBR=%s   dstU=%s srcTR=%s"
              % (x, col(tile(tl + 1), x), col(tile(pt + 3), x),
                 col(tile(tl), x), col(tile(pt + 2), x)))
