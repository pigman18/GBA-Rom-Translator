#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""静态盘点 v2：按真实步长 0x18 走窗口模板表（只读原盘）。

字段（已由 dump 0x081BB874 定出）：
  +0x08 字体/宽度类  +0x09 textMode（worker 读它）  +0x0B 恒 0（真模板）
  +0x0C tileData（层内写砖基址 = 该 BG 层 char 块基址）
  +0x10 tilemap（层内 map 基址）
层基址 = 0x06000000 + charBase*0x4000；某地址在层内的**砖号** = (addr - 层基址)/32。
⇒ 引擎字模区恒占该层砖号 [1,513)；tilemap 占 [map_idx, map_idx+宽*高)。
本脚本据此判定每个模板「[514,768) 是否可站」——纯静态、不采样。
"""
import os
import struct
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"C:\code\GBA-Rom-Translator"
ROM_PATH = os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba")
BASE = 0x08000000
VRAM = 0x06000000
CB = 0x4000
TILE = 32
ANCHOR = 0x081BB3DC
LO, HI = 0x081BB000, 0x081BC000
STRIDE = 0x18


def ok(rom, a):
    if not (LO <= a < HI - STRIDE):
        return False
    o = a - BASE
    td = struct.unpack_from("<I", rom, o + 0x0C)[0]
    return VRAM <= td < 0x06018000 and td % TILE == 0 and rom[o + 0x0B] == 0


def main():
    rom = open(ROM_PATH, "rb").read()
    a = ANCHOR
    while ok(rom, a - STRIDE):
        a -= STRIDE
    start = a
    tpls = []
    while ok(rom, a):
        tpls.append(a)
        a += STRIDE
    print("模板表：0x%08X .. 0x%08X  共 %d 条（步长 0x%X）\n"
          % (start, tpls[-1], len(tpls), STRIDE))

    modes = Counter()
    rows = []
    for t in tpls:
        o = t - BASE
        mode = rom[o + 9]
        font = rom[o + 8]
        td = struct.unpack_from("<I", rom, o + 0x0C)[0]
        tm = struct.unpack_from("<I", rom, o + 0x10)[0]
        cb = (td - VRAM) // CB
        mode = mode & 3 if mode < 8 else mode
        layer = VRAM + cb * CB
        map_idx = (tm - layer) // TILE if tm >= layer else -1
        modes[mode] += 1
        rows.append((t, mode, font, cb, td, tm, map_idx))

    print("textMode 分布：%s\n" % sorted(modes.items()))
    print("%-10s %4s %4s %6s %-10s %-10s %8s  %s"
          % ("tpl", "tm", "+08", "charBase", "tileData", "tilemap", "map砖号", "[514,768)"))
    for t, mode, font, cb, td, tm, mi in rows:
        if mi < 0 or mi >= 1024:
            free = "map在层外"
        elif mi >= 768 or mi + 1 <= 514:
            free = "空 ✓"
        else:
            free = "⚠ 被 map 占"
        print("%08X  %4d %4d %6d    %08X  %08X %8s  %s"
              % (t, mode, font, cb, td, tm, mi if 0 <= mi < 1024 else ">1023", free))

    print("\n--- tm==1（走池子、撞号的候选）---")
    for t, mode, font, cb, td, tm, mi in rows:
        if mode == 1:
            print("  %08X  charBase=%d  tileData=%08X  map砖号=%s"
                  % (t, cb, td, mi if 0 <= mi < 1024 else ">1023"))
    print("\n--- tm==3（官方网格 = 从不撞）---")
    for t, mode, font, cb, td, tm, mi in rows:
        if mode == 3:
            print("  %08X  charBase=%d  tileData=%08X  map砖号=%s"
                  % (t, cb, td, mi if 0 <= mi < 1024 else ">1023"))
    print("\n--- tm==0 / tm==2 ---")
    for t, mode, font, cb, td, tm, mi in rows:
        if mode in (0, 2):
            print("  %08X  tm=%d charBase=%d  tileData=%08X  map砖号=%s"
                  % (t, mode, cb, td, mi if 0 <= mi < 1024 else ">1023"))


if __name__ == "__main__":
    main()
