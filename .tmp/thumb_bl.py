# -*- coding: utf-8 -*-
"""thumb_bl.py — 扫 ROM 找所有 bl 到指定地址的调用点（Thumb BL，2×16bit 编码）。

Thumb BL:
  hw1 = 11110 S imm10      (0xF000 | S<<10 | imm10)
  hw2 = 11 J1 1 J2 imm11   (0xF800 | J1<<13 | J2<<11 | imm11)
  S = hw1>>10 & 1 ; I1 = J1^S ; I2 = J2^S
  offset = (S<<24|I1<<23|I2<<22|imm10<<12|imm11<<1)  符号扩展
  target = (pc + 4) + offset      pc = 该指令地址
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 0x08000000


def scan(rom, targets):
    res = {t: [] for t in targets}
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
        imm11 = hw2 & 0x7FF
        i1 = (j1 ^ s) ^ 1          # I1 = ¬(J1 ⊕ S)
        i2 = (j2 ^ s) ^ 1          # I2 = ¬(J2 ⊕ S)
        v = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
        if s:
            v -= (1 << 25)
        pc = BASE + off
        tgt = (pc + 4 + v) & 0xFFFFFFFF
        if tgt in res:
            res[tgt].append(pc)
    return res


if __name__ == "__main__":
    rom = open(os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba"),
               "rb").read()
    targets = [int(x, 16) for x in sys.argv[1:]]
    r = scan(rom, targets)
    for t in targets:
        print("bl -> %08X : %d 处" % (t, len(r[t])))
        for p in r[t][:40]:
            print("     @%08X" % p)
