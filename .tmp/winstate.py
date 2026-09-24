# -*- coding: utf-8 -*-
"""winstate.py <tag> -- 读我方状态槽 + 找 EWRAM 里的窗口 + 打印 IWRAM 串内容。"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag = sys.argv[1]
ew = (T / ("drive_%s_ewram.bin" % tag)).read_bytes()
iw = (T / ("drive_%s_iwram.bin" % tag)).read_bytes()
E, I = 0x02000000, 0x03000000


def u16(a):
    return struct.unpack_from("<H", ew, a - E)[0]


def u8(a):
    return ew[a - E]


def u32(a):
    return struct.unpack_from("<I", ew, a - E)[0]


print("--- 我方状态槽 ---")
print("V8_CURSOR(0x0203FF42) = %d" % u16(0x0203FF42))
print("V8_PHASE (0x0203FF44) = %d" % u16(0x0203FF44))
print("V8_PHROW (0x0203FF46) = 0x%04X" % u16(0x0203FF46))
print("V8_LASTT (0x0203FF48) = %d" % u16(0x0203FF48))
print("V8Q_MAGIC(0x0203FF4A) = 0x%04X" % u16(0x0203FF4A))
print("V8Q_WIN  (0x0203FF4C) = %08X" % u32(0x0203FF4C))
print("V8Q_TPL  (0x0203FF58) = %08X" % u32(0x0203FF58))
print("DIAG_CNT (0x0203FF50) = %d" % u32(0x0203FF50))
print("V6_BYPASS(0x0203FEB8) = %d" % u8(0x0203FEB8))

print("\n--- EWRAM 里的窗口（模板 = 0x081BB874） ---")
TPL = 0x081BB874
for off in range(0, len(ew) - 0x28, 2):
    if struct.unpack_from("<I", ew, off)[0] == TPL:
        W = E + off
        tp = struct.unpack_from("<I", ew, off + 0x10)[0]
        print("@%08X tm=%d fn=%d C=%d D=%d E=%d pal=%d tb=%d off18=%d tX=%d idx=%d ptr=%08X" % (
            W, ew[off + 0x0A], ew[off + 0x0B], ew[off + 0x0C], ew[off + 0x0D],
            ew[off + 0x0E], ew[off + 0x0F],
            struct.unpack_from("<H", ew, off + 0x16)[0],
            struct.unpack_from("<H", ew, off + 0x18)[0],
            ew[off + 0x1B], struct.unpack_from("<H", ew, off + 0x14)[0], tp))
        if I <= tp < I + len(iw):
            raw = iw[tp - I:tp - I + 64]
            print("      IWRAM 串: %s" % raw[:40].hex(" "))
        elif 0x08000000 <= tp:
            print("      ROM 指针偏移 0x%06X" % (tp - 0x08000000))
