# -*- coding: utf-8 -*-
"""tpl_fields.py — 模板字段结构解析 + 三张寄存器表的真身验证。

由 `0x08002878` 逐指令推得（本脚本负责交叉验证）：
    层号 = tpl[+0]                      （查三张表取 REG 指针）
    REG_BGxCNT(层) = tpl[+3] | (tpl[+2]<<8) | (tpl[+1]<<2)
    GBA BGxCNT: bit0-1 priority | bit2-3 charBase | bit6 mosaic
                | bit7 8bpp | bit8-12 screenBase | bit14-15 size
  ⇒ tpl[+1] = charBase ,  tpl[+2] = screenBase
  ⇒ tpl[+0x0C] = tileData  = 0x06000000 + charBase*0x4000
     tpl[+0x10] = tilemap   = 0x06000000 + screenBase*0x800
"""
from __future__ import annotations

import os
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba")
BASE = 0x08000000
VRAM = 0x06000000
rom = open(ROM, "rb").read()

TAB_A = 0x081B344C      # 写 0 的第一个表
TAB_B = 0x081B345C      # 写 0 的第二个表
TAB_C = 0x081B343C      # 写 BGxCNT 的表


def u32(a):
    return struct.unpack_from("<I", rom, a - BASE)[0]


print("=" * 90)
print("三张寄存器表（层号 → REG 地址）")
print("=" * 90)
for nm, t in (("A(写0)", TAB_A), ("B(写0)", TAB_B), ("C(写CNT)", TAB_C)):
    print("  表%s @%08X : %s" % (nm, t, "  ".join("%08X" % u32(t + i * 4) for i in range(4))))

# 注册表
REG = 0x081BB8D4
reg = {}
for i in range(64):
    p = REG + i * 8
    tpl, k = u32(p), u32(p + 4)
    if not (0x081BB3DC <= tpl < 0x081BB8C0):
        break
    reg[k] = tpl

print()
print("=" * 90)
print("53 条模板：字段结构（bgId/charBase/screenBase/prio/font/tm）+ 交叉验证")
print("=" * 90)
print("%-5s %-9s %-5s %-8s %-10s %-5s %-5s %-4s %-8s %-8s %s" %
      ("key", "tpl", "bgId", "charBase", "screenBase", "prio", "font", "tm", "tileData", "tilemap", "验证"))
bad = 0
for k in sorted(reg):
    a = reg[k]
    o = a - BASE
    bg = rom[o + 0]
    cb = rom[o + 1]
    sb = rom[o + 2]
    prio = rom[o + 3] & 3
    font = rom[o + 8]
    tm = rom[o + 9]
    td = u32(a + 0x0C)
    mp = u32(a + 0x10)
    e_td = VRAM + cb * 0x4000
    e_mp = VRAM + sb * 0x800
    ok = "OK"
    if td != e_td:
        ok = "td≠!%08X" % e_td
        bad += 1
    if mp and mp != e_mp:
        ok += " mp≠!%08X" % e_mp
        bad += 1
    print("%-5s %08X %-5d %-8d %-10d %-5d %-5d %-4d %-8s %-8s %s" %
          ("0x%02X" % k, a, bg, cb, sb * 0x800 + VRAM - VRAM and sb, prio, font, tm,
           "%08X" % td, "%08X" % mp, ok))
print()
print("交叉验证失败项：%d（0 = charBase/screenBase 与 tileData/tilemap 完全自洽）" % bad)
