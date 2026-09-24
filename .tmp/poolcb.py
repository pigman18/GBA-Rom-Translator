# -*- coding: utf-8 -*-
"""poolcb.py — tm1 池的**唯一结构性风险**精确核查（2026-09-22）

我方池 = 本层 charBase 块的第 POOL_LO..POOL_HI 号砖 ⇒ 物理落在 **charBase+1 块**
（块 = 0x4000 B = 512 砖）。所以只要同屏存在另一层，其字模区覆盖该块，就是
「拿别人的美术区写字」，必花屏。两种覆盖方式：

  ① charBase_M == charBase_L + 1      —— M 的字模区正好是那一块
  ② charBase_M == charBase_L 且 M 是 8bpp（BGxCNT bit7=1）—— M 占两块

（v10 用的 CHAR_REGION=0x8000 把「块」当「两块的并集」，对 4bpp 层是过近似，
  会报 k45/k46 那种假阳性；本脚本按 4bpp=1 块 / 8bpp=2 块精确算。）
"""
import os
import struct
from collections import defaultdict

ROOT = r"C:\code\GBA-Rom-Translator"
BASE, VRAM = 0x08000000, 0x06000000
rom = open(os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba"), "rb").read()
TARGET = int(os.environ.get("TARGET", "0x080027DC"), 16)
POOL_LO, POOL_HI = 521, 1024
BLK = 0x4000


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


FUNCS = sorted({BASE + off for off in range(0, len(rom) - 6, 2)
                if (u16(BASE + off) & 0xFF00) == 0xB500
                and (is_bx_lr(u16(BASE + off - 2)) or is_pop_pc(u16(BASE + off - 2))
                     or is_b(u16(BASE + off - 2)) or u16(BASE + off - 2) == 0)})
print("函数起始：", len(FUNCS))


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
        hw1, hw2 = u16(BASE + off), u16(BASE + off + 2)
        if (hw1 & 0xF800) != 0xF000 or (hw2 & 0xF800) != 0xF800:
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
    return dict(bg=rom[o], cb=cb, font=rom[o + 8], tm=rom[o + 9],
                td=u32(a + 0x0C), cnt=cnt, bpp8=bool(cnt & 0x80))


pages = defaultdict(list)
for s in sorted(scan_bl(TARGET)):
    k = find_key_imm(s)
    if k is None or k not in reg:
        continue
    pages[owner(s)].append((s, k))

bad, clean, n8 = [], 0, 0
for o in sorted(pages, key=lambda x: (x is None, x or 0)):
    layers = [(k, tinfo(k)) for _, k in pages[o]]
    tm1 = [(k, t) for k, t in layers if t["tm"] == 1]
    if not tm1:
        continue
    hits = []
    for k, t in tm1:
        if t["cb"] >= 3:
            hits.append("key%-2d cb3 ⇒ 池落 OBJ 区（该层不画）" % k)
            continue
        # 我方池的物理块号
        blk = t["cb"] + 1
        for k2, t2 in layers:
            if k2 == k:
                continue
            span = 2 if t2["bpp8"] else 1
            if t2["cb"] <= blk < t2["cb"] + span:
                hits.append("key%-2d(池块%d) vs key%-2d(cb%d%s) ⇒ 字模区被覆盖"
                            % (k, blk, k2, t2["cb"], " 8bpp/2块" if t2["bpp8"] else ""))
        if t["bpp8"]:
            n8 += 1
    if hits:
        bad.append((o, layers, hits))
    else:
        clean += 1

for o, layers, hits in bad:
    print("!! 界面 %s （%d 层：%s）"
          % (("%08X" % o) if o else "???", len(layers),
             ",".join("BG%d/k%d/cb%d%s/tm%d" % (t["bg"], k, t["cb"],
                                                "+" if t["bpp8"] else "", t["tm"])
                      for k, t in layers)))
    for h in hits:
        print("     ", h)

print()
print("界面总数（含 tm1 层）:", clean + len(bad))
print("干净界面:", clean, " 有覆盖风险界面:", len(bad), " 其中 tm1 层是 8bpp 的:", n8)
