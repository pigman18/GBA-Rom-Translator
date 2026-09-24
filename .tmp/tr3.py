# -*- coding: utf-8 -*-
"""tr3.py <tag> — 解析 CHS_TRACE 块，输出窗口表 + 每字 (win,cx,cy,TB,off,t0,t1,phase,adv,tm,ch)"""
import struct, sys
from pathlib import Path
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag = sys.argv[1]
ew = (T / ("drive_%s_ewram.bin" % tag)).read_bytes()
base = 0x3C000
w = struct.unpack_from("<2048I", ew, base)
assert w[0] == 0x32584441, "magic %08X" % w[0]
print("magic ok  glyph_calls=%d ring=%d win_uniq=%d dup=%d" % (w[1], w[2], w[3], w[4]))
# 窗口表 w8.. 24*8
n_win = 0
for i in range(24):
    o = 8 + i*8
    win, tpl, tdata, map_, cnt, tb, cxcy, _ = w[o:o+8]
    if win == 0:
        continue
    n_win += 1
    print("WIN%d win=%08X tpl=%08X tdata=%08X map=%08X cnt=%d TB=%d CUR=(%d,%d)"
          % (i, win, tpl, tdata, map_, cnt, tb, cxcy & 0xFF, (cxcy >> 8) & 0xFF))
# 环形 w200..
print("---- 前 90 条字形记录 ----")
prev = None
n = w[2]
for i in range(min(n, 400)):
    o = 200 + i*5
    a,b,c,d,e = w[o:o+5]
    cx = b & 0xFF; cy = (b>>8)&0xFF; ctx=(b>>16)&0xFF; cty=(b>>24)&0xFF
    tb = c & 0xFFFF; off = (c>>16)&0xFFFF
    t0 = d & 0xFFFF; t1 = (d>>16)&0xFFFF
    ph = e & 0xFF; adv=(e>>8)&0xFF; tm=(e>>16)&0xFF; ch=(e>>24)&0xFF
    print("%3d win=%08X cx=%2d cy=%2d ctx=%2d cty=%2d TB=%3d off=%3d t0=%4d t1=%4d ph=%d adv=%d tm=%d ch=%02X"
          % (i, a, cx, cy, ctx, cty, tb, off, t0, t1, ph, adv, tm, ch))
