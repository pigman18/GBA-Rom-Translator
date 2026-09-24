# -*- coding: utf-8 -*-
"""dupchk.py <tag> -- 判「池号被跨行复用」= 塌/撞的硬证据。

设计约定：池游标单调 ⇒ 每个字拿到全新砖号 ⇒ **同一砖号不允许多行出现**。
本脚本：按 BG0 的 map，逐格打号；统计每个号出现的 (行,列) 集合；
       跨行重复 / 同行远距离重复 = 撞。
"""
import struct
import sys
from collections import defaultdict
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")


def main(tag):
    vram = (T / f"drive_{tag}_vram.bin").read_bytes()
    io = struct.unpack_from("<H", (T / f"drive_{tag}_io.bin").read_bytes(), 0)[0]
    cnt = struct.unpack_from("<H", (T / f"drive_{tag}_io.bin").read_bytes(), 0x08)[0]
    hofs = struct.unpack_from("<H", (T / f"drive_{tag}_io.bin").read_bytes(), 0x10)[0]
    vofs = struct.unpack_from("<H", (T / f"drive_{tag}_io.bin").read_bytes(), 0x12)[0]
    cb, sb, size = (cnt >> 2) & 3, (cnt >> 8) & 0x1F, (cnt >> 14) & 3
    w, h = {0: (32, 32), 1: (64, 32), 2: (32, 64), 3: (64, 64)}[size]
    off = sb * 0x800
    print("%s DISPCNT=%04X BG0CNT=%04X cb%d sb%d sz%d HOFS=%d VOFS=%d"
          % (tag, io, cnt, cb, sb, size, hofs, vofs))
    bg0on = (io >> 8) & 1
    if not bg0on:
        print("!! BG0 not enabled in DISPCNT")

    # 物理屏幕 30x20 格（240/8=30, 160/8=20）
    pos = defaultdict(list)
    grid = {}
    for sy in range(20):
        for sx in range(30):
            mx = (sx + hofs // 8) % w
            my = (sy + vofs // 8) % h
            e = struct.unpack_from("<H", vram, off + (my * w + mx) * 2)[0]
            grid[(sy, sx)] = (e & 0x3FF, (e >> 12) & 0xF)
            pos[e & 0x3FF].append((sy, sx))

    print("\n== map 号网格（屏幕格坐标；. = tile0/空）==")
    for sy in range(20):
        row = []
        for sx in range(30):
            n, pal = grid[(sy, sx)]
            row.append("%4d" % n if n else "   .")
        print("s%02d " % sy + "".join(row))

    print("\n== 调色板 bank 网格 ==")
    for sy in range(20):
        row = []
        for sx in range(30):
            n, pal = grid[(sy, sx)]
            row.append("%2d" % pal if n else " .")
        print("s%02d " % sy + "".join(row))

    print("\n== 跨行复用（同号出现在 >=2 个不同屏幕行）==")
    bad = 0
    for n, lst in sorted(pos.items()):
        rows = sorted({r for r, _ in lst})
        if n and len(rows) >= 2:
            bad += 1
            print("  tile %4d  rows=%s  cells=%s" % (n, rows, lst[:14]))
    print("跨行复用号数 = %d" % bad)

    print("\n== 同行重复（同号在同一行出现 >=2 次）==")
    bad2 = 0
    for n, lst in sorted(pos.items()):
        byrow = defaultdict(list)
        for r, c in lst:
            byrow[r].append(c)
        for r, cs in byrow.items():
            if n and len(cs) >= 2 and max(cs) - min(cs) >= 1:
                bad2 += 1
                print("  tile %4d  row=%d  cols=%s" % (n, r, cs))
    print("同行重复号数 = %d" % bad2)

    hi = [n for n in pos if n >= 521]
    print("\n>=521 的号数 = %d, 范围 %s..%s"
          % (len(hi), min(hi) if hi else "-", max(hi) if hi else "-"))
    lo = sorted(n for n in pos if 0 < n < 521)
    print("<521 的号（引擎自用）: %s%s" % (lo[:40], " ..." if len(lo) > 40 else ""))


if __name__ == "__main__":
    main(sys.argv[1])
