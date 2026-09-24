# -*- coding: utf-8 -*-
"""ewscan.py — 从 EWRAM dump 里捞活着的 TextPrinter 结构，读它的 win[0x16]=TILE_BASE。

判据：+0x00 = 模板指针 ∈ ROM 区；+0x0A = textMode ≤3；+0x0B = fontNum ≤7；
      +0x20 = tileData ∈ VRAM 或全 0；且 +0x16 是个像样的号。
目的：把「引擎给这个窗口的字形缓存基址」与「我们观测到的边框基址(512/603)」对上关系。
"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")


def scan(tag):
    p = T / f"drive_{tag}_ewram.bin"
    if not p.exists():
        print(tag, "无 ewram.bin")
        return
    e = p.read_bytes()
    iw = T / f"drive_{tag}_iwram.bin"
    iwd = iw.read_bytes() if iw.exists() else b""
    out = []
    for off in range(0, len(e) - 0x28, 4):
        tpl = struct.unpack_from("<I", e, off)[0]
        if not (0x08000000 <= tpl < 0x08800000):
            continue
        tm = e[off + 0x0A]
        fn = e[off + 0x0B]
        if tm > 3 or fn > 7:
            continue
        base = struct.unpack_from("<H", e, off + 0x16)[0]
        tofs = struct.unpack_from("<H", e, off + 0x18)[0]
        cx = e[off + 0x1A]
        ctx = e[off + 0x1B]
        cy = e[off + 0x1C]
        cty = e[off + 0x1D]
        td = struct.unpack_from("<I", e, off + 0x20)[0]
        if not (td == 0 or 0x06000000 <= td < 0x06020000 or 0x02000000 <= td < 0x02040000):
            continue
        out.append((off, tpl, tm, fn, base, tofs, cx, ctx, cy, cty, td))
    print("=" * 100)
    print("%s  EWRAM %d bytes  命中 %d" % (tag, len(e), len(out)))
    for o in out[:24]:
        off, tpl, tm, fn, base, tofs, cx, ctx, cy, cty, td = o
        print("  EWRAM+%05X tpl=%08X tm=%d fn=%d TILE_BASE=%5d TILE_OFF=%5d "
              "curX=%2d tX=%2d curY=%2d tY=%2d td=%08X"
              % (off, tpl, tm, fn, base, tofs, cx, ctx, cy, cty, td))
    # 顺带：单例 0x03000328/0x0300032C 在 IWRAM 里
    if iwd:
        for a in (0x328, 0x32C, 0x32E):
            if a + 4 <= len(iwd):
                print("   IWRAM 0x0300%04X = %08X" % (a, struct.unpack_from("<I", iwd, a)[0]))


for t in sys.argv[1:]:
    scan(t)
