# -*- coding: utf-8 -*-
"""ewwin.py — 精确捞 TextPrinter：win[0x00] 必须落在模板表 [0x081BB3DC, 0x081BB8D4)。

输出每个窗口的 tm / font / TILE_BASE / TILE_OFFSET / cursor，用来回答：
  · 引擎给 tm1 窗口的字形缓存基址 TILE_BASE 是多少？
  · font 决定 needed=256/512，缓存区 = [TILE_BASE, TILE_BASE+needed)
  · 边框(512/603) 与这个区间什么关系？
"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
TPL_LO, TPL_HI = 0x081BB3DC, 0x081BB8D4


def scan(tag):
    p = T / f"drive_{tag}_ewram.bin"
    if not p.exists():
        print(tag, "no ewram")
        return
    e = p.read_bytes()
    hits = []
    for off in range(0, len(e) - 0x28, 2):
        tpl = struct.unpack_from("<I", e, off)[0]
        if not (TPL_LO <= tpl < TPL_HI):
            continue
        tm = e[off + 0x0A]
        fn = e[off + 0x0B]
        if tm > 3 or fn > 7:
            continue
        hits.append((off, tpl, tm, fn,
                     struct.unpack_from("<H", e, off + 0x16)[0],
                     struct.unpack_from("<H", e, off + 0x18)[0],
                     e[off + 0x1A], e[off + 0x1B], e[off + 0x1C], e[off + 0x1D],
                     struct.unpack_from("<I", e, off + 0x04)[0]))
    print("=" * 104)
    print("%s  命中 %d 个窗口" % (tag, len(hits)))
    for h in hits[:20]:
        off, tpl, tm, fn, base, tofs, cx, tx, cy, ty, txt = h
        need = 512 if fn in (1, 4) else (256 if fn in (2, 3, 5) else 0)
        print("  +%05X tpl=%08X(#%02d) tm=%d fn=%d TB=%5d OFF=%5d "
              "need=%3d 区=[%d,%d)  cur(%2d,%2d) t(%2d,%2d) txt=%08X"
              % (off, tpl, (tpl - TPL_LO) // 0x18, tm, fn, base, tofs,
                 need, base, base + need, cx, cy, tx, ty, txt))


for t in sys.argv[1:]:
    scan(t)
