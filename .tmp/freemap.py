# -*- coding: utf-8 -*-
"""freemap.py -- 用**原盘 dump**统计「引擎自己用掉的 VRAM 砖」，再算连续空档。

「用掉」= 任一使能 BG 的 map 引用的砖地址（含地图表自身占用的字节区间）。
取所有 o_* 页面的**并集**（不是 savestate，也不是单页快照）。
输出：连续空档（>= 32 砖）按绝对地址 + 各 charBlock 内的相对号列出。

用法: python .tmp/freemap.py
"""
import struct
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
VRAM_BASE = 0x06000000
BLK = 0x4000
TAGS = ["o_title", "o_menu", "o_bag", "o_party", "o_sum2", "o_info", "o_moves"]


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
            for b in range(off, off + w * h * 2, 32):     # 地图表本身
                s.add(VRAM_BASE + b)
            for y in range(h):
                for x in range(w):
                    e = struct.unpack_from("<H", vram, off + (y * w + x) * 2)[0]
                    s.add(VRAM_BASE + cb * BLK + (e & 0x3FF) * 32)
    return s


def main():
    s = used()
    lo_a, hi_a = VRAM_BASE, VRAM_BASE + 0x10000
    print("引擎已用砖 %d 个 (原盘 7 页并集)" % len(s))
    runs = []
    a = lo_a
    while a < hi_a:
        if a in s:
            a += 32
            continue
        b = a
        while b < hi_a and b not in s:
            b += 32
        if b - a >= 32 * 8:
            runs.append((a, b))
        a = b
    for a, b in runs:
        print("  空档 [%08X,%08X) %4d 砖 %4d B  cb1号[%4d,%4d) cb2号[%4d,%4d) cb3号[%4d,%4d)"
              % (a, b, (b - a) // 32, b - a,
                 (a - VRAM_BASE - BLK) // 32, (b - VRAM_BASE - BLK) // 32,
                 (a - VRAM_BASE - 2 * BLK) // 32, (b - VRAM_BASE - 2 * BLK) // 32,
                 (a - VRAM_BASE - 3 * BLK) // 32, (b - VRAM_BASE - 3 * BLK) // 32))


if __name__ == "__main__":
    main()
