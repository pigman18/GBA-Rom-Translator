# -*- coding: utf-8 -*-
"""allpaths.py — 三条建窗通路的界面层清单（决定我方池能否安放）。

通路：
  P1 0x080027DC(key)        r0 = key      「配一个 BG 层」
  P2 0x08002C28(win,key)    r1 = key      「建窗口」
  P3 0x0806F158(win,key)    r1 = key      「通用建窗」

对每个 owner 函数输出其所有层的 (bg, cb, tm, font, tileData, screenblock)，
并做「真冲突」判定：
  对某 tm1 层 L，池物理 = [td_L + 514*32, td_L + 1024*32)
  冲突条件 = 同屏存在另一层 M 且 cb_M == cb_L + 1
             （M 的 tile 号 0..511 恰好覆盖池物理区）
  次冲突   = 该池与同屏任何 screenblock 相交（chs_collect_blocked 已处理）
"""
import os
import struct
from collections import defaultdict

ROOT = r"C:\code\GBA-Rom-Translator"
BASE, VRAM = 0x08000000, 0x06000000
rom = open(os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba"), "rb").read()
POOL_LO, POOL_HI = 514, 1024
REG = 0x081BB8D4
TPLS, TPLN = 0x081BB3DC, 0x081BB8C0


def u16(a):
    return struct.unpack_from("<H", rom, a - BASE)[0]


def u32(a):
    return struct.unpack_from("<I", rom, a - BASE)[0]


def is_bx_lr(hw):
    return (hw & 0xFF87) == 0x4700


def is_pop_pc(hw):
    return (hw & 0xFE00) == 0xBC00 and (hw & 0x0100) != 0


def build_funcs():
    s = set()
    for off in range(2, len(rom) - 6, 2):
        hw = u16(BASE + off)
        if (hw & 0xFF00) != 0xB500:
            continue
        p = u16(BASE + off - 2)
        if is_bx_lr(p) or is_pop_pc(p) or (p & 0xF800) == 0xE000 or p == 0:
            s.add(BASE + off)
    return sorted(s)


FUNCS = build_funcs()


def owner(site):
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
        h1 = u16(BASE + off)
        if (h1 & 0xF800) != 0xF000:
            continue
        h2 = u16(BASE + off + 2)
        if (h2 & 0xF800) != 0xF800:
            continue
        s = (h1 >> 10) & 1
        v = (s << 24) | ((((h2 >> 13) & 1) ^ s ^ 1) << 23) \
            | ((((h2 >> 11) & 1) ^ s ^ 1) << 22) | ((h1 & 0x3FF) << 12) \
            | ((h2 & 0x7FF) << 1)
        if s:
            v -= (1 << 25)
        if ((BASE + off + 4 + v) & 0xFFFFFFFF) == target:
            out.append(BASE + off)
    return out


def imm_to_reg(site, reg):
    """往前找给 reg 的立即数（movs / adds rN,#0）。"""
    a = site - 2
    for _ in range(16):
        if a < BASE:
            break
        hw = u16(a)
        want = 0x2000 | (reg << 8)
        if (hw & 0xFF00) == want:
            return hw & 0xFF
        if (hw & 0xFFC0) == 0x1C00 and (hw & 7) == reg and ((hw >> 6) & 7) == 0:
            return 0            # mov reg, r0 —— key 在 r0，另找
        a -= 2
    return None


reg_map = {}
for i in range(64):
    p = REG + i * 8
    tpl, k = u32(p), u32(p + 4)
    if not (TPLS <= tpl < TPLN):
        break
    reg_map[k] = tpl


def tinfo(k):
    a = reg_map[k]
    o = a - BASE
    sb, cb, p3 = rom[o + 2], rom[o + 1], rom[o + 3]
    cnt = p3 | (sb << 8) | (cb << 2)
    size = (cnt >> 14) & 3
    sba = VRAM + ((cnt >> 8) & 0x1F) * 0x800
    return dict(bg=rom[o], cb=cb, font=rom[o + 8], tm=rom[o + 9], td=u32(a + 0x0C),
                sba=sba, sbe=sba + {0: 0x800, 1: 0x1000, 2: 0x1000, 3: 0x2000}[size])


def iv(a, b):
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


pages = defaultdict(set)
for name, target, reg in (("P1", 0x080027DC, 0), ("P2", 0x08002C28, 1),
                          ("P3", 0x0806F158, 1)):
    sites = scan_bl(target)
    hit = 0
    for s in sites:
        k = imm_to_reg(s, reg)
        if k is None or k not in reg_map:
            continue
        hit += 1
        pages[owner(s)].add(k)
    print("%s 0x%08X：调用点 %d，解出 key %d" % (name, target, len(sites), hit))

print()
bad1 = bad2 = 0
for o in sorted(pages, key=lambda x: (x is None, x or 0)):
    ks = sorted(pages[o])
    layers = [(k, tinfo(k)) for k in ks]
    tm1 = [(k, t) for k, t in layers if t["tm"] == 1]
    flag = ""
    for k, t in tm1:
        if t["cb"] >= 3:
            flag += " [k%d cb3无解]" % k
            bad1 += 1
            continue
        for k2, t2 in layers:
            if k2 == k:
                continue
            if t2["cb"] == t["cb"] + 1:
                flag += " [k%d撞k%d(cb%d=%d+1)]" % (k, k2, t2["cb"], t["cb"])
                bad1 += 1
        lo, hi = t["td"] + POOL_LO * 32, t["td"] + POOL_HI * 32
        for k2, t2 in layers:
            if iv((t2["sba"], t2["sbe"]), (lo, hi)):
                flag += " [k%d池撞k%d-map%08X]" % (k, k2, t2["sba"])
                bad2 += 1
    print("界面 %s  %d 层：%s%s"
          % (("%08X" % o) if o else "???", len(layers),
             ",".join("BG%d/k%d/cb%d/tm%d/f%d" % (t["bg"], k, t["cb"], t["tm"], t["font"])
                      for k, t in layers), flag))

print()
print("真冲突（cb+1 或 cb3）：", bad1)
print("池撞 screenblock：", bad2, "（运行时 chs_collect_blocked 已挖）")
