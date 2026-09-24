# -*- coding: utf-8 -*-
"""winmap.py <tag> -- 每个打印窗口：tileData vs **它实际画在哪一层**。

CHS_TRACE 窗口表每条 8 word：(win, tpl, tileData, map, cnt, tb, cx, cy)
本脚本再用 IO dump 的 BGxCNT 反查 map 指针落在哪个层的 screen block，
从而得出「该窗口文字实际显示在哪一层 / 该层 charBase 是多少」。
对比 tileData 就能判定：写砖基址该用 tileData 还是层 charBase。

用法: python .tmp/winmap.py t_moves
"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
TRACE, TR_TBL, TR_W, TR_N = 0x3C000, 8, 8, 24
VRAM_BASE = 0x06000000


def main(tag):
    e = (T / f"drive_{tag}_ewram.bin").read_bytes()
    io = (T / f"drive_{tag}_io.bin").read_bytes()
    disp = struct.unpack_from("<H", io, 0)[0]
    bgs = []
    for i in range(4):
        cnt = struct.unpack_from("<H", io, 0x08 + 2 * i)[0]
        on = (disp >> (8 + i)) & 1
        cb, sb, size = (cnt >> 2) & 3, (cnt >> 8) & 0x1F, (cnt >> 14) & 3
        w, h = {0: (32, 32), 1: (64, 32), 2: (32, 64), 3: (64, 64)}[size]
        lo = VRAM_BASE + sb * 0x800
        bgs.append((i, on, cb, lo, lo + w * h * 2))
    print("== %s  DISPCNT=%04X" % (tag, disp))
    for i, on, cb, lo, hi in bgs:
        print("   BG%d on=%d charBase=%d screenBlock=[%08X,%08X)" % (i, on, cb, lo, hi))
    seen = {}
    for k in range(TR_N):
        o = TRACE + (TR_TBL + k * TR_W) * 4
        w, tpl, td, mp, cnt, tb, cx, cy = struct.unpack_from("<IIIIIIII", e, o)
        ok = (0x02000000 <= w < 0x02040000) or (0x03000000 <= w < 0x03008000)
        if not ok or cnt == 0:
            continue
        key = (td, mp)
        rec = seen.setdefault(key, [0, w, tpl, 0, 0])
        rec[0] += cnt
        rec[3] = cx
        rec[4] = cy
    for (td, mp), (cnt, w, tpl, cx, cy) in sorted(seen.items(), key=lambda x: -x[1][0]):
        owner = "-"
        for i, on, cb, lo, hi in bgs:
            if lo <= mp < hi:
                owner = "BG%d(charBase=%d)" % (i, cb)
        print("   win=%08X tpl=%08X tileData=%08X map=%08X cnt=%3d  map 属于 %s"
              % (w, tpl, td, mp, cnt, owner))


if __name__ == "__main__":
    main(sys.argv[1])
