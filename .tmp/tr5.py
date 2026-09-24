# -*- coding: utf-8 -*-
"""tr5.py <tag> — 打印 CHS_TRACE 逐条记录：win/tm/TB/t0/t1/相位/字符，
   并算出 t0 落在**该窗口自身 VB 字节地址**上的位置（判断是否越出本窗口 charBlock）。"""
import struct, sys
from pathlib import Path
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
tag = sys.argv[1]
filt = sys.argv[2] if len(sys.argv) > 2 else None
ew = (T / ("drive_%s_ewram.bin" % tag)).read_bytes()
base = ew.find(b"ADX2")
if base < 0:
    print("NO TRACE"); sys.exit(1)
w = struct.unpack_from("<2048I", ew, base)
print("magic@0x%05X calls=%d ring=%d win_uniq=%d dup=%d" % (base, w[1], w[2], w[3], w[4]))
wt = {}
for i in range(24):
    o = 8 + i * 8
    win, tpl, td, mp, cnt, tb, cxcy, _ = w[o:o + 8]
    if win:
        wt[win] = dict(tpl=tpl, td=td, mp=mp, cnt=cnt, tb=tb,
                       cx=cxcy & 0xFF, cy=(cxcy >> 8) & 0xFF)
        print("WIN %08X tpl=%08X TData=%08X map=%08X n=%3d TB=%d" %
              (win, tpl, td, mp, cnt, tb))
n = min(w[2], 256)
rows = []
for i in range(n):
    o = 200 + i * 5
    a, b, c, d, e = w[o:o + 5]
    cx = b & 0xFF; cy = (b >> 8) & 0xFF; ctx = (b >> 16) & 0xFF; cty = (b >> 24) & 0xFF
    tb = c & 0xFFFF; off = (c >> 16) & 0xFFFF
    t0 = d & 0xFFFF; t1 = (d >> 16) & 0xFFFF
    ph = e & 0xFF; adv = (e >> 8) & 0xFF; tm = (e >> 16) & 0xFF; ch = (e >> 24) & 0xFF
    rows.append((a, tm, cx, cy, ctx, cty, tb, off, t0, t1, ph, adv, ch))
if filt:
    rows = [r for r in rows if ("%08X" % r[0]).endswith(filt)]
print("--- %d recs ---" % len(rows))
print("win      tm cx cy ctx cty   TB   off    t0    t1  ph adv ch  tdata    |  t0字节      层内off")
for r in rows:
    a, tm, cx, cy, ctx, cty, tb, off, t0, t1, ph, adv, ch = r
    td = wt.get(a, {}).get("td", 0)
    lay = td & ~0x3FFF  # 该层 charBlock 基址（16KB 对齐）
    ab = td + t0 * 32
    print("%08X %2d %2d %2d %3d %3d %4d %5d %5d %5d %3d %3d %02X %08X | %08X  %5d"
          % (a, tm, cx, cy, ctx, cty, tb, off, t0, t1, ph, adv, ch, td, ab, t0))
