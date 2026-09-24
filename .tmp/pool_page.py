# -*- coding: utf-8 -*-
"""pool_page.py — 逐界面核：tm1 文本层的「我方池」[td+514*32, td+1024*32)
与该界面所有 BG 层 screenblock（tilemap 内存）是否相交。

复用 bg_layer_map.py 的调用点/归属扫描；只加 screenblock 维度。
BGxCNT = tpl[3] | (tpl[2]<<8) | (tpl[1]<<2)；size = bit14-15。
"""
import os
import struct
from collections import defaultdict

ROOT = r"C:\code\GBA-Rom-Translator"
BASE, VRAM = 0x08000000, 0x06000000
rom = open(os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba"), "rb").read()
TARGET = 0x080027DC
POOL_LO, POOL_HI = 514, 1024


def u16(a):
    return struct.unpack_from("<H", rom, a - BASE)[0]


def u32(a):
    return struct.unpack_from("<I", rom, a - BASE)[0]


def scan_bl(target):
    out = []
    for off in range(0, len(rom) - 4, 2):
        hw1 = u16(BASE + off)
        if (hw1 & 0xF800) != 0xF000:
            continue
        hw2 = u16(BASE + off + 2)
        if (hw2 & 0xF800) != 0xF800:
            continue
        s = (hw1 >> 10) & 1
        v = (s << 24) | (((hw2 >> 13 & 1) ^ s ^ 1) << 23) \
            | (((hw2 >> 11 & 1) ^ s ^ 1) << 22) | ((hw1 & 0x3FF) << 12) \
            | ((hw2 & 0x7FF) << 1)
        if s:
            v -= (1 << 25)
        pc = BASE + off
        if ((pc + 4 + v) & 0xFFFFFFFF) == target:
            out.append(pc)
    return out


def find_key_imm(site):
    a = site - 2
    for _ in range(14):
        if a < BASE:
            break
        hw = u16(a)
        if (hw & 0xFF00) == 0x2000:
            return hw & 0xFF
        a -= 2
    return None


def owner(site, lim=0x600):
    a = site - 2
    while a > site - lim:
        if (u16(a) & 0xFF00) == 0xB500:
            hw = u16(a - 2)
            if (hw & 0xFF87) == 0x4700 or (hw & 0xFE00) == 0xBC00 \
               or (hw & 0xF800) == 0xE000 or hw == 0x0000:
                return a
        a -= 2
    return None


reg = {}
for i in range(64):
    p = 0x081BB8D4 + i * 8
    tpl, k = u32(p), u32(p + 4)
    if not (0x081BB3DC <= tpl < 0x081BB8C0):
        break
    reg[k] = tpl


def tinfo(k):
    a = reg[k]
    o = a - BASE
    sb, cb, p3 = rom[o + 2], rom[o + 1], rom[o + 3]
    cnt = p3 | (sb << 8) | (cb << 2)
    size = (cnt >> 14) & 3
    sba = VRAM + ((cnt >> 8) & 0x1F) * 0x800
    return dict(bg=rom[o], cb=cb, font=rom[o + 8], tm=rom[o + 9],
                td=u32(a + 0x0C), mp=u32(a + 0x10),
                sba=sba, sbe=sba + {0: 0x800, 1: 0x1000, 2: 0x1000, 3: 0x2000}[size])


pages = defaultdict(list)
for s in sorted(scan_bl(TARGET)):
    k = find_key_imm(s)
    if k is None or k not in reg:
        continue
    pages[owner(s)].append((s, k))

bad = 0
for o in sorted(pages, key=lambda x: (x is None, x or 0)):
    layers = [(k, tinfo(k)) for _, k in pages[o]]
    tm1 = [(k, t) for k, t in layers if t["tm"] == 1]
    if not tm1:
        continue
    print("界面 %s  （%d 层：%s）"
          % (("%08X" % o) if o else "???", len(layers),
             ",".join("BG%d/k%d/cb%d/tm%d" % (t["bg"], k, t["cb"], t["tm"]) for k, t in layers)))
    for k, t in tm1:
        if t["cb"] >= 3:
            print("   ⚠ key%-2d cb=3 ⇒ 池无处安放" % k)
            bad += 1
            continue
        lo, hi = t["td"] + POOL_LO * 32, t["td"] + POOL_HI * 32
        hits = []
        for k2, t2 in layers:
            if t2["sba"] < hi and t2["sbe"] > lo:
                hits.append("BG%d/k%d map[%08X,%08X)" % (t2["bg"], k2, t2["sba"], t2["sbe"]))
        if hits:
            bad += 1
            print("   ⚠ key%-2d 池[%08X,%08X) 被 screenblock 占：%s"
                  % (k, lo, hi, " | ".join(hits)))
        else:
            print("   ✓ key%-2d 池[%08X,%08X) 干净（%d 砖）" % (k, lo, hi, POOL_HI - POOL_LO))
    print()

print("有问题的 tm1 层数：", bad)
