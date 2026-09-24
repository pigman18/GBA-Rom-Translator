# -*- coding: utf-8 -*-
"""trdump.py — 读 mgba_drive 的 ewram dump，打印 CHS_TRACE 环形记录。

用法:
    python .tmp/trdump.py <tag> [--win 0x03004170] [--tm 1] [--t0-min 900]

布局（diag_log.h）：
  w0 magic 'ADX2'  w1 glyph_calls  w2 ring filled  w3 win_uniq  w4 dup
  w8..w199  窗口表 24 × {win, tpl, tileData, map, count, 0,0,0}
  w200..    环形 369 × 5 字
      w+0 win
      w+1 cx | cy<<8 | ctx<<16 | cty<<24
      w+2 tb | off<<12 | prev<<16
      w+3 t0 | t1<<16
      w+4 phase | adv<<8 | tm<<16 | ch<<24
"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
TR = 0x3C000          # 0x0203C000 - 0x02000000


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def main():
    tag = sys.argv[1]
    opt = dict(a.split("=", 1) if "=" in a else (a, True)
               for a in sys.argv[2:] if a.startswith("--"))
    ew = (T / ("drive_%s_ewram.bin" % tag)).read_bytes()
    g = lambda o: u32(ew, TR + o)

    if g(0) != 0x32445841 and g(0) != ord("A") | (ord("D") << 8) | (ord("X") << 16) | (ord("2") << 24):
        print("magic = 0x%08X (期望 'ADX2')" % g(0))
    print("magic=0x%08X calls=%d filled=%d win_uniq=%d dup=%d"
          % (g(0), g(4), g(8), g(12), g(16)))

    print("---- 窗口表 ----")
    for i in range(24):
        o = 0x20 + i * 32
        win, tpl, td, mp, cnt = g(o), g(o + 4), g(o + 8), g(o + 12), g(o + 16)
        if win == 0 and cnt == 0:
            continue
        print("  #%-2d win=0x%08X tpl=0x%08X tileData=0x%08X map=0x%08X n=%d"
              % (i, win, tpl, td, mp, cnt))

    print("---- 环形 ----")
    n = 369
    rows = []
    for i in range(n):
        o = 0x320 + i * 20
        win = g(o)
        a1 = g(o + 4)
        a2 = g(o + 8)
        a3 = g(o + 12)
        a4 = g(o + 16)
        if win == 0 and a1 == 0 and a2 == 0 and a3 == 0 and a4 == 0:
            continue
        cx, cy = a1 & 0xFF, (a1 >> 8) & 0xFF
        ctx, cty = (a1 >> 16) & 0xFF, (a1 >> 24) & 0xFF
        tb, off, prev = a2 & 0xFFF, (a2 >> 12) & 0xF, (a2 >> 16) & 0xFFFF
        t0, t1 = a3 & 0xFFFF, (a3 >> 16) & 0xFFFF
        phase, adv = a4 & 0xFF, (a4 >> 8) & 0xFF
        tm, ch = (a4 >> 16) & 0xFF, (a4 >> 24) & 0xFF
        rows.append((win, cx, cy, ctx, cty, tb, off, prev, t0, t1,
                     phase, adv, tm, ch))

    fw = opt.get("--win")
    if fw:
        fw = int(fw, 16) if isinstance(fw, str) and fw.startswith("0x") else int(fw)
        rows = [r for r in rows if r[0] == fw]
    if "--tm" in opt:
        rows = [r for r in rows if r[12] == int(opt["--tm"])]
    if "--t0-min" in opt:
        rows = [r for r in rows if r[8] >= int(opt["--t0-min"])]
    for r in rows:
        print("  win=%08X cx=%-3d cy=%-2d ctx=%-2d cty=%-2d tb=0x%03X off=%-3d "
              "prev=%-5d t0=%-5d t1=%-5d ph=%d adv=%d tm=%d ch=0x%02X"
              % (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9],
                 r[10], r[11], r[12], r[13]))


if __name__ == "__main__":
    main()
