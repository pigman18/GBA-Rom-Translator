# -*- coding: utf-8 -*-
"""ringdump.py <tag> [win_hex] — 按写入顺序打印 CHS_TRACE 环形记录。"""
import sys
import struct
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag = sys.argv[1]
want = int(sys.argv[2], 16) if len(sys.argv) > 2 else None
ew = (T / ("drive_%s_ewram.bin" % tag)).read_bytes()
TR = 0x3C000
cnt = struct.unpack_from("<I", ew, TR + 8)[0]
print("magic=%08X glyph_calls=%d ring=%d uniq_win=%d"
      % tuple(struct.unpack_from("<IIII", ew, TR)))
RING = TR + 200 * 4
N = 256
for k in range(N):
    rec = struct.unpack_from("<IIIII", ew, RING + k * 20)
    if rec[0] == 0:
        continue
    win, xy, tb_off, t01, pa = rec
    cx, cy = xy & 0xFF, (xy >> 8) & 0xFF
    ctx, cty = (xy >> 16) & 0xFF, (xy >> 24) & 0xFF
    tb, off, prev = tb_off & 0xFFF, (tb_off >> 12) & 0xF, (tb_off >> 16) & 0xFFFF
    t0, t1 = t01 & 0xFFFF, (t01 >> 16) & 0xFFFF
    phase, adv, tm, ch = pa & 0xFF, (pa >> 8) & 0xFF, (pa >> 16) & 0xFF, (pa >> 24) & 0xFF
    if want is not None and win != want:
        continue
    print("  #%03d win=%08X tb=%d off=%d cx=%d cy=%d ctx=%d cty=%d t0=%d t1=%d prev=%d phase=%d adv=%d tm=%d ch=%02X"
          % (k, win, tb, off, cx, cy, ctx, cty, t0, t1, prev, phase, adv, tm, ch))
