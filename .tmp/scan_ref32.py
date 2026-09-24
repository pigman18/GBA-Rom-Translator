# -*- coding: utf-8 -*-
"""scan_ref32.py — 扫 ROM 找所有「4 字节 LE 等于目标地址」的位置（常量池/函数指针表）。

用法: python .tmp/scan_ref32.py 0x08004228 0x0800424C
"""
import os
import struct
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 0x08000000
rom = open(os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba"),
           "rb").read()


def u16(a):
    return struct.unpack_from("<H", rom, a - BASE)[0]


def is_prologue(a):
    return (u16(a) & 0xFF00) == 0xB500


def is_end(a):
    hw = u16(a)
    if (hw & 0xFF87) == 0x4700:
        return True
    if (hw & 0xF800) == 0xE000:
        return ((hw >> 8) & 0xF) in (0xE, 0xF, 0x1, 0xD)
    if (hw & 0xFE00) == 0xBC00:
        return True
    return False


def owner(site, lim=0x600):
    a = site - 2
    end = site - lim
    while a > end:
        if is_prologue(a):
            if is_end(a - 2) or u16(a - 2) == 0x0000:
                return a
        a -= 2
    return None


def refs(target):
    out = []
    for off in range(0, len(rom) - 4, 2):
        if struct.unpack_from("<I", rom, off)[0] == target:
            out.append(BASE + off)
    return out


for t in sys.argv[1:]:
    tv = int(t, 16)
    hits = refs(tv)
    print("=" * 84)
    print("引用 %08X 的位置：%d 处" % (tv, len(hits)))
    print("=" * 84)
    g = defaultdict(list)
    for h in hits:
        g[owner(h)].append(h)
    for o in sorted(g, key=lambda x: (x is None, x or 0)):
        print("  owner %-9s : %s" % (("%08X" % o) if o else "???",
                                     " ".join("%08X" % x for x in sorted(g[o]))))
    print()
