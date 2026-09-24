# -*- coding: utf-8 -*-
"""key_of_win.py — 提取「界面函数 → 模板 key」映射。

`0x08002C28(win, key)` 是窗口创建入口：先填默认值，再查注册表设 win[0]=模板。
  ⇒ 调用前给 **r1** 的赋值 = 模板 key。

注册表 0x081BB8D4 起，项 8 字节 = (tpl_ptr @+0, key @+4)。
"""
from __future__ import annotations

import os
import struct
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 0x08000000
VRAM = 0x06000000
rom = open(os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba"),
           "rb").read()
REG = 0x081BB8D4          # 第一项的 tpl_ptr 字段
N_MAX = 64


def u16(a):
    return struct.unpack_from("<H", rom, a - BASE)[0]


def u32(a):
    return struct.unpack_from("<I", rom, a - BASE)[0]


def load_registry():
    """{key: tpl_addr}"""
    out = {}
    for i in range(N_MAX):
        p = REG + i * 8
        tpl = u32(p)
        k = u32(p + 4)
        if not (0x081BB3DC <= tpl < 0x081BB8C0):
            break
        out[k] = tpl
    return out


def tpl_info(tpl):
    o = tpl - BASE
    return dict(tm=rom[o + 9], font=rom[o + 8],
                td=struct.unpack_from("<I", rom, o + 0x0C)[0],
                mp=struct.unpack_from("<I", rom, o + 0x10)[0])


def decode_r1(addr):
    """判断 addr 处指令是否给 r1 赋值。"""
    hw = u16(addr)
    if (hw & 0xFF00) == 0x2100:                       # movs r1, #imm8
        return "imm#%d" % (hw & 0xFF)
    if (hw & 0xFFC0) == 0x1C00 and (hw & 7) == 1:     # adds r1, rN, #0
        return "mov r%d" % ((hw >> 3) & 7)
    if (hw & 0xF800) == 0x4800:                       # ldr r1, [pc, #imm]
        pc = (addr + 4) & ~3
        return "lit%08X" % u32(pc + (hw & 0xFF) * 4)
    if (hw & 0xF800) == 0x6800:                       # ldr r1, [rN, #imm]
        return "mem r%d+%d" % ((hw >> 3) & 7, ((hw & 0x7C0) >> 6) * 4)
    if (hw & 0xF800) == 0x9800:                       # ldr r1, [sp, #imm]
        return "sp+%d" % ((hw & 0xFF) * 4)
    if (hw & 0xFF00) == 0x4600:                       # mov r1, rN (hi)
        rd = (hw & 7) | (((hw >> 7) & 1) << 3)
        rm = ((hw >> 3) & 7) | (((hw >> 6) & 1) << 3)
        if rd == 1:
            return "movhi r%d" % rm
    return None


def find_key(site):
    a = site - 2
    for _ in range(12):
        if a < BASE:
            break
        r = decode_r1(a)
        if r:
            return r, a
        a -= 2
    return None, None


def owner(site, lim=0x400):
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


def main():
    sys.argv = sys.argv
    # bl 扫描
    sites = []
    n = len(rom)
    for off in range(0, n - 4, 2):
        hw1 = struct.unpack_from("<H", rom, off)[0]
        if (hw1 & 0xF800) != 0xF000:
            continue
        hw2 = struct.unpack_from("<H", rom, off + 2)[0]
        if (hw2 & 0xF800) != 0xF800:
            continue
        s = (hw1 >> 10) & 1
        imm10 = hw1 & 0x3FF
        j1 = (hw2 >> 13) & 1
        j2 = (hw2 >> 11) & 1
        i1 = (j1 ^ s) ^ 1
        i2 = (j2 ^ s) ^ 1
        v = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | ((hw2 & 0x7FF) << 1)
        if s:
            v -= (1 << 25)
        pc = BASE + off
        if ((pc + 4 + v) & 0xFFFFFFFF) == 0x08002C28:
            sites.append(pc)

    reg = load_registry()
    print("=" * 104)
    print("注册表：%d 个 key（0x%02X..0x%02X）" % (len(reg), min(reg), max(reg)))
    print("=" * 104)
    print("%-11s %-6s %-3s %-5s %-5s %-10s %-7s %s" %
          ("key", "tpl", "tm", "font", "cb", "tileData", "下一块", "备注"))
    for k in sorted(reg):
        ti = tpl_info(reg[k])
        cb = (ti["td"] - VRAM) // 0x4000 if VRAM <= ti["td"] < VRAM + 0x10000 else -1
        note = ""
        if ti["tm"] == 1:
            note = "★tm1 预取图集"
        elif ti["tm"] == 3:
            note = "tm3 网格"
        elif ti["tm"] == 2:
            note = "tm2"
        elif ti["tm"] == 0:
            note = "tm0 官方自画"
        print("%-11s %08X %-3d %-5d %-5d %08X %-7s %s" %
              ("0x%02X(%d)" % (k, k), reg[k], ti["tm"], ti["font"], cb,
               ti["td"], "cb%d" % ((cb + 1) % 4) if cb >= 0 else "-", note))

    print()
    print("=" * 104)
    print("`0x08002C28(win,key)` 的调用点 → key（r1）")
    print("=" * 104)
    print("%-11s %-11s %-14s %-6s %s" % ("调用点", "所属函数", "r1 来源", "key", "命中模板"))
    print("-" * 104)
    byo = defaultdict(list)
    for s in sorted(sites):
        src, at = find_key(s)
        o = owner(s)
        key = None
        if src and src.startswith("imm#"):
            key = int(src[4:])
        tag = ""
        if key is not None and key in reg:
            ti = tpl_info(reg[key])
            cb = (ti["td"] - VRAM) // 0x4000 if VRAM <= ti["td"] < VRAM + 0x10000 else -1
            tag = "key 0x%02X → %08X tm%d cb%d td=%08X" % (key, reg[key], ti["tm"], cb, ti["td"])
        elif key is not None:
            tag = "!! key %d 不在注册表" % key
        print("%08X  %-11s %-14s %-6s %s" %
              (s, ("%08X" % o) if o else "???", src or "?", key if key is not None else "?", tag))
        if o:
            byo[o].append(key)
    print()
    print("=" * 104)
    print("按「所属函数」归组（同一函数建多个窗口）")
    print("=" * 104)
    for o in sorted(byo):
        print("  %08X : keys = %s" %
              (o, ", ".join(("0x%02X" % k) if k is not None else "?" for k in byo[o])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
