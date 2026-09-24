# -*- coding: utf-8 -*-
"""扫 ROM 找「窗口模板注册表」基址的引用点，定位查表函数。"""
import os
import re
import struct
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba")
BASE = 0x08000000
rom = open(ROM, "rb").read()

CANDS = [0x081BB8C8, 0x081BB8D0, 0x081BB8C0, 0x081BB8D4]


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


for target in CANDS:
    hits = []
    for off in range(0, len(rom) - 4, 2):
        if struct.unpack_from("<I", rom, off)[0] == target:
            hits.append(BASE + off)
    if not hits:
        continue
    print("=" * 90)
    print("引用 %08X 的点：%d 处" % (target, len(hits)))
    print("=" * 90)
    grouped = defaultdict(list)
    for h in hits:
        o = owner(h)
        grouped[o if o else 0].append(h)
    for o in sorted(grouped, key=lambda x: (x == 0, x)):
        print("  owner %s :  %s" % (("%08X" % o) if o else "???",
                                    " ".join("%08X" % x for x in sorted(grouped[o]))))
    print()

# 附带：找所有「模板表基址 0x081BB3DC」的引用（除注册表外）
print("=" * 90)
print("引用 0x081BB3DC（模板表首条）的点")
print("=" * 90)
for off in range(0, len(rom) - 4, 2):
    if struct.unpack_from("<I", rom, off)[0] == 0x081BB3DC:
        a = BASE + off
        print("  @%08X  owner %s" % (a, ("%08X" % owner(a)) if owner(a) else "???"))
