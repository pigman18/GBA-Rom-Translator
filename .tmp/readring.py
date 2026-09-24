# -*- coding: utf-8 -*-
"""readring.py <tag> -- 读 EWRAM 里 chs_print 诊断环（0x0203FF50 计数 / 0x0203FF5C ring）。"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag = sys.argv[1]
ew = (T / ("drive_%s_ewram.bin" % tag)).read_bytes()
E = 0x02000000
cnt = struct.unpack_from("<I", ew, 0x0203FF50 - E)[0]
idx = struct.unpack_from("<H", ew, 0x0203FFCC - E)[0]
print("总调用数 = %d   ring idx = %d" % (cnt, idx))
n = 14
print("\n--- ring（按写入先后 = 从 idx 起绕一圈）---")
for k in range(n):
    i = (idx + k) % n
    o = 0x0203FF5C - E + i * 8
    ptr, v = struct.unpack_from("<II", ew, o)
    code = v & 0xFFFF
    tid = (v >> 16) & 0xFFFF
    print("  [%2d] ptr=%08X code=%04X idx=%3d" % (i, ptr, code, tid))
