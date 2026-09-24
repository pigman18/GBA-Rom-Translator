# -*- coding: utf-8 -*-
"""bg_layer_map.py — 「界面 → 各 BG 层 charBase 集合」（本轮最终判据）。

依据（全部逐指令实证 + 100% 交叉验证，见 .tmp/tpl_fields.py）：
  · `0x080027DC(key)` = 按注册表取模板，配 **一个 BG 层**：
        0x08002878(tpl): REG_BGxCNT = tpl[3]|(tpl[2]<<8)|(tpl[1]<<2)
                         REG_BGxHOFS/VOFS = 0
    （三张表 = 0x081B343C/344C/345C → 04000008..0E / 10..1C / 12..1E，已验）
  · 模板字段：+0=bgId  +1=charBase  +2=screenBase  +3=prio
              +8=font  +9=textMode  +0C=tileData  +10=tilemap
  · 引擎字模缓存（单例）：写 tileData + [1,513)*32
        ⇒ 该层号 1..511 + **下一块号 0**
  · 我方字模放「文本层自己的号 [513,1024)」⇒ 物理 = **(charBase+1) 块**

冲突判据（纯静态）：
  设文本层 charBase = C。同界面另一 BG 层 charBase = C'。
    该层号 0..1023 物理覆盖 [(C'), (C')+2) 块。
    我方占 (C+1) 块。
  ⇒ 冲突 ⟺ C' ∈ {C, C+1}
     （C'=C：它的号 512..1023 = C+1 块；C'=C+1：它的号 0..511 = C+1 块）
"""
from __future__ import annotations

import os
import struct
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 0x08000000
VRAM = 0x06000000
rom = open(os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba"),
           "rb").read()
TARGET = 0x080027DC


def u16(a):
    return struct.unpack_from("<H", rom, a - BASE)[0]


def u32(a):
    return struct.unpack_from("<I", rom, a - BASE)[0]


def scan_bl(target):
    out = []
    for off in range(0, len(rom) - 4, 2):
        hw1 = struct.unpack_from("<H", rom, off)[0]
        if (hw1 & 0xF800) != 0xF000:
            continue
        hw2 = struct.unpack_from("<H", rom, off + 2)[0]
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


def decode_r0(addr):
    hw = u16(addr)
    if (hw & 0xFF00) == 0x2000:
        return ("imm", hw & 0xFF)
    if (hw & 0x7FF) == 0x0000 and (hw & 0xF800) == 0x1C00:
        return ("mov r0", None)
    if (hw & 0xF800) == 0x4800:
        return ("lit", u32(((addr + 4) & ~3) + (hw & 0xFF) * 4))
    if (hw & 0xF800) == 0x6800:
        return ("mem r%d+%d" % ((hw >> 3) & 7, ((hw & 0x7C0) >> 6) * 4), None)
    if (hw & 0xF800) == 0x9800:
        return ("sp+%d" % ((hw & 0xFF) * 4), None)
    if (hw & 0xFF00) == 0x4600:
        rd = (hw & 7) | (((hw >> 7) & 1) << 3)
        rm = ((hw >> 3) & 7) | (((hw >> 6) & 1) << 3)
        if rd == 0:
            return ("mov r%d" % rm, None)
    return None


def find_key(site):
    a = site - 2
    for _ in range(14):
        if a < BASE:
            break
        r = decode_r0(a)
        if r:
            return r
        a -= 2
    return None


def owner(site, lim=0x600):
    a = site - 2
    end = site - lim
    while a > end:
        if (u16(a) & 0xFF00) == 0xB500:
            hw = u16(a - 2)
            if (hw & 0xFF87) == 0x4700 or (hw & 0xFE00) == 0xBC00 \
               or (hw & 0xF800) == 0xE000 or hw == 0x0000:
                return a
        a -= 2
    return None


# 注册表
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
    return dict(bg=rom[o], cb=rom[o + 1], sb=rom[o + 2], prio=rom[o + 3] & 3,
                font=rom[o + 8], tm=rom[o + 9], td=u32(a + 0x0C), mp=u32(a + 0x10))


sites = scan_bl(TARGET)
print("=" * 100)
print("`0x080027DC(key)` 调用点：%d 个（每个 = 配一个 BG 层）" % len(sites))
print("=" * 100)

byo = defaultdict(list)
unk = []
for s in sorted(sites):
    src = find_key(s)
    key = None
    if src and src[0] == "imm":
        key = src[1]
    o = owner(s)
    if key is None:
        unk.append((s, o, src))
        continue
    byo[o].append((s, key))

print("%-11s %-11s %-5s %-5s %-8s %-5s %-4s %-9s %-9s %s" %
      ("调用点", "界面函数", "key", "bgId", "charBase", "prio", "tm", "tileData", "tilemap", "font"))
print("-" * 100)
for s in sorted(sites):
    src = find_key(s)
    key = src[1] if (src and src[0] == "imm") else None
    o = owner(s)
    if key is not None and key in reg:
        t = tinfo(key)
        print("%08X  %-11s 0x%02X  %-5d %-8d %-5d %-4d %08X  %08X  %d" %
              (s, ("%08X" % o) if o else "???", key, t["bg"], t["cb"], t["prio"],
               t["tm"], t["td"], t["mp"], t["font"]))
    else:
        print("%08X  %-11s %-5s %-5s %-8s  (key 未静态识别: %s)" %
              (s, ("%08X" % o) if o else "???", "-", "-", "-", src))

print()
print("=" * 100)
print("按「界面函数」归组 → 每界面的 BG 层 charBase 集合 + 冲突判定")
print("=" * 100)
for o in sorted(byo, key=lambda x: (x is None, x or 0)):
    layers = {}
    for s, k in byo[o]:
        t = tinfo(k)
        layers.setdefault(t["bg"], []).append((k, t))
    if not layers:
        continue
    txt = []
    cinfo = {}
    for bg in sorted(layers):
        for k, t in layers[bg]:
            cinfo.setdefault(t["cb"], []).append("BG%d(k%d,tm%d)" % (bg, k, t["tm"]))
    for cb in sorted(cinfo):
        txt.append("cb%d:%s" % (cb, ",".join(cinfo[cb])))
    # 找该界面的文本层（tm1）
    verdicts = []
    for bg in sorted(layers):
        for k, t in layers[bg]:
            if t["tm"] != 1:
                continue
            C = t["cb"]
            bad = [(b2, k2, t2) for b2 in layers for k2, t2 in layers[b2]
                   if t2["cb"] in (C, C + 1) and (b2, k2) != (bg, k)]
            if bad:
                verdicts.append("⚠ 文本层 BG%d key%d(C=%d) 的下一块 cb%d 被 %s 占" %
                                (bg, k, C, C + 1,
                                 ",".join("BG%d(k%d,C=%d)" % (b2, k2, t2["cb"]) for b2, k2, t2 in bad)))
            else:
                verdicts.append("✓ 文本层 BG%d key%d(C=%d) 下一块 cb%d 干净" % (bg, k, C, C + 1))
    print("  界面 %s" % (("%08X" % o) if o else "???"))
    print("     层配置：%s" % "  ".join(txt))
    for v in verdicts:
        print("     %s" % v)
    print()

print("=" * 100)
print("key 未静态识别的调用点：%d 个（key 来自参数/内存，需另查）" % len(unk))
print("=" * 100)
for s, o, src in unk:
    print("  %08X  owner %s   r0 来源 = %s" % (s, ("%08X" % o) if o else "???", src))
