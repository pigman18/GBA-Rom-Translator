# -*- coding: utf-8 -*-
"""pool_page3.py — 用「全 ROM 函数起始表」做归属，逐界面核 tm1 池的两类冲突。

函数起始 = `push {..,lr}` 且前一指令是函数尾（bx lr / pop pc / b / 对齐 0）。
归属 = 最大的 ≤ 调用点的函数起始。
"""
import os
import struct
from collections import defaultdict

ROOT = r"C:\code\GBA-Rom-Translator"
BASE, VRAM = 0x08000000, 0x06000000
rom = open(os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba"), "rb").read()
TARGET = 0x080027DC
POOL_LO, POOL_HI = 514, 1024
CHAR_REGION = 0x8000


def u16(a):
    return struct.unpack_from("<H", rom, a - BASE)[0]


def u32(a):
    return struct.unpack_from("<I", rom, a - BASE)[0]


def is_bx_lr(hw):
    return (hw & 0xFF87) == 0x4700


def is_pop_pc(hw):
    return (hw & 0xFE00) == 0xBC00 and (hw & 0x0100) != 0


def is_b(hw):
    return (hw & 0xF800) == 0xE000


def build_funcs():
    """返回排序后的函数起始地址表（只收合法 prologue）。"""
    starts = set()
    for off in range(0, len(rom) - 6, 2):
        hw = u16(BASE + off)
        if (hw & 0xFF00) != 0xB500:      # push {.., lr}
            continue
        prev = u16(BASE + off - 2)
        if is_bx_lr(prev) or is_pop_pc(prev) or is_b(prev) or prev == 0x0000:
            starts.add(BASE + off)
    return sorted(starts)


FUNCS = build_funcs()
print("识别到函数起始：", len(FUNCS))


def owner(site):
    lo, hi = 0, len(FUNCS) - 1
    best = None
    for f in FUNCS:
        if f <= site:
            best = f
        else:
            break
    return best


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
                td=u32(a + 0x0C), cnt=cnt, sba=sba,
                sbe=sba + {0: 0x800, 1: 0x1000, 2: 0x1000, 3: 0x2000}[size])


def iv(a, b):
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


pages = defaultdict(list)
for s in sorted(scan_bl(TARGET)):
    k = find_key_imm(s)
    if k is None or k not in reg:
        continue
    pages[owner(s)].append((s, k))

nA = nB = nc3 = 0
nclean = 0
for o in sorted(pages, key=lambda x: (x is None, x or 0)):
    layers = [(k, tinfo(k)) for _, k in pages[o]]
    tm1 = [(k, t) for k, t in layers if t["tm"] == 1]
    if not tm1:
        continue
    print("界面 %s （%d 层：%s）"
          % (("%08X" % o) if o else "???", len(layers),
             ",".join("BG%d/k%d/cb%d/tm%d" % (t["bg"], k, t["cb"], t["tm"])
                      for k, t in layers)))
    for k, t in tm1:
        if t["cb"] >= 3:
            print("   xx key%-2d cb=3 ⇒ 池无处安放" % k)
            nc3 += 1
            continue
        lo, hi = t["td"] + POOL_LO * 32, t["td"] + POOL_HI * 32
        hA = ["BG%d/k%d map[%08X,%08X)" % (t2["bg"], k2, t2["sba"], t2["sbe"])
              for k2, t2 in layers if iv((t2["sba"], t2["sbe"]), (lo, hi))]
        hB = []
        for k2, t2 in layers:
            if k2 == k:
                continue
            r = (t2["td"], t2["td"] + CHAR_REGION)
            ov = iv(r, (lo, hi))
            if ov:
                hB.append("BG%d/k%d/cb%d char[%08X,%08X) 重叠 0x%X"
                          % (t2["bg"], k2, t2["cb"], r[0], r[1], ov))
        if hA or hB:
            print("   !! key%-2d 池[%08X,%08X)" % (k, lo, hi))
            if hA:
                nA += 1
                print("        A 撞 tilemap: " + " | ".join(hA))
            if hB:
                nB += 1
                print("        B 撞他层字模区: " + " | ".join(hB))
        else:
            nclean += 1

print()
print("干净 tm1 层：", nclean)
print("A 撞 tilemap 的层：", nA, "（chs_collect_blocked 已挖掉）")
print("B 撞他层字模区的层：", nB, " <-- >0 则 v10 池位置需重定")
print("cb3 无解的层：", nc3)
