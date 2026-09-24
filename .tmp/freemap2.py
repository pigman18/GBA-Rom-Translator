# -*- coding: utf-8 -*-
"""freemap2.py -- 同 freemap，但打印所有 >= 2 砖的空档，并按「人口可达范围」汇总。

人口可达范围（由窗口 tileData 决定的 char 块基址给号空间 [0,1024)）：
  · 人口 0：tileData=0x06004000 ⇒ 地址 [0x06004000,0x0600C000)，块内号 = (A-0x06004000)/32
  · 人口 1：tileData=0x06008000 ⇒ 地址 [0x06008000,0x06010000)，块内号 = (A-0x06008000)/32
  · 人口 2：tileData=0x06000000 ⇒ 地址 [0x06000000,0x06008000)，块内号 = A/32

用法: python .tmp/freemap2.py
"""
import struct
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
VRAM_BASE = 0x06000000
BLK = 0x4000
TAGS = ["o_title", "o_menu", "o_bag", "o_party", "o_sum2", "o_info", "o_moves"]

DOM = {0: (0x06004000, 0x0600C000),
       1: (0x06008000, 0x06010000),
       2: (0x06000000, 0x06008000)}


def blob(tag, name):
    p = T / f"drive_{tag}_{name}.bin"
    return p.read_bytes() if p.exists() else None


def used():
    s = set()
    for tag in TAGS:
        io, vram = blob(tag, "io"), blob(tag, "vram")
        if io is None or vram is None:
            continue
        disp = struct.unpack_from("<H", io, 0)[0]
        for i in range(4):
            cnt = struct.unpack_from("<H", io, 0x08 + 2 * i)[0]
            if not (disp >> (8 + i)) & 1:
                continue
            cb, sb, size = (cnt >> 2) & 3, (cnt >> 8) & 0x1F, (cnt >> 14) & 3
            w, h = {0: (32, 32), 1: (64, 32), 2: (32, 64), 3: (64, 64)}[size]
            off = sb * 0x800
            for b in range(off, off + w * h * 2, 32):
                s.add(VRAM_BASE + b)
            for y in range(h):
                for x in range(w):
                    e = struct.unpack_from("<H", vram, off + (y * w + x) * 2)[0]
                    s.add(VRAM_BASE + cb * BLK + (e & 0x3FF) * 32)
    return s


def main():
    s = used()
    print("引擎已用砖 %d 个 (原盘 7 页并集)" % len(s))
    for dom in (0, 1, 2):
        lo, hi = DOM[dom]
        # 收集本域可达范围内的连续空档
        runs = []
        a = lo
        while a < hi:
            if a in s:
                a += 32
                continue
            b = a
            while b < hi and b not in s:
                b += 32
            runs.append((a, b))
            a = b
        tot = sum((b - a) // 32 for a, b in runs)
        print("\n=== 人口 %d  可达 [%08X,%08X)  空砖合计 %d ===" % (dom, lo, hi, tot))
        for a, b in runs:
            n = (b - a) // 32
            if n < 2:
                continue
            print("   [%08X,%08X) %3d 砖  块内号[%4d,%4d)  槽 %d"
                  % (a, b, n, (a - lo) // 32, (b - lo) // 32, n // 2))


if __name__ == "__main__":
    main()
