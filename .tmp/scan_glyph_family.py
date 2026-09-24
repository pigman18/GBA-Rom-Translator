#!/usr/bin/env python3
"""扫描 DrawGlyphTiles 双胞胎的调用点，并列出所有「同构字形绘制函数」族。

发现：0x08003630 与 0x080033B4 前 32 字节完全相同（push/mov r9/mov r8/push/sub sp,#12/
adds r4,r0/mov r8,r1/ldr [sp+0x28] ... /lsls r2,#24/lsrs r5,#24/...）。
⇒ 同一个源文件编译出的两个实例（或 tm0/tm2 各一份）。

本脚本：
  1. 列出 0x080033B4 的所有 BL 调用点
  2. 全 ROM 搜索「字形绘制函数族」—— 特征：以 b5f0 464f 4646 b4c0 b083 1c04 4688 开头
"""
from __future__ import annotations

import os
import struct
import sys

ROOT = r"C:\code\GBA-Rom-Translator"
ROM_PATH = os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba")

FAMILY_SIG = bytes.fromhex("f0b54f464646c0b483b0041c8846")


def bl_target(rom: bytes, off: int):
    if off + 4 > len(rom):
        return None
    hw1 = struct.unpack_from("<H", rom, off)[0]
    hw2 = struct.unpack_from("<H", rom, off + 2)[0]
    if (hw1 >> 11) != 0b11110 or (hw2 >> 14) != 0b11 or ((hw2 >> 12) & 1) != 1:
        return None
    S = (hw1 >> 10) & 1
    imm10 = hw1 & 0x3FF
    J1 = (hw2 >> 13) & 1
    J2 = (hw2 >> 11) & 1
    imm11 = hw2 & 0x7FF
    I1 = (~(J1 ^ S)) & 1
    I2 = (~(J2 ^ S)) & 1
    imm = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
    if imm & 0x1000000:
        imm -= 0x2000000
    return (0x08000000 + off + 4 + imm) & 0xFFFFFFFF


def main() -> int:
    rom = open(ROM_PATH, "rb").read()
    print(f"ROM {len(rom)} bytes")
    print(f"特征字节 = {FAMILY_SIG.hex()}")

    # 1) 找族
    print("\n=== 字形绘制函数族（特征匹配）===")
    fam = []
    pos = 0
    while True:
        i = rom.find(FAMILY_SIG, pos)
        if i < 0:
            break
        fam.append(0x08000000 + i)
        pos = i + 1
    for a in fam:
        print(f"  0x{a:08X}")

    # 2) 各族成员的调用点
    print("\n=== 各成员的 BL 调用点 ===")
    for a in fam:
        hits = []
        for off in range(0, len(rom) - 4, 2):
            if bl_target(rom, off) == a:
                hits.append(0x08000000 + off)
        print(f"  0x{a:08X}  <- {len(hits)} 处: " + " ".join(f"0x{h:08X}" for h in hits))

    # 3) 各成员的跳转表（+0x44 处 ldr r1,[pc,#8] 的池）
    print("\n=== 各成员内部结构速览 ===")
    for a in fam:
        off = a - 0x08000000
        print(f"\n--- 0x{a:08X} ---")
        for x in range(off, off + 0x50, 2):
            v = struct.unpack_from("<H", rom, x)[0]
            print(f"  0x{0x08000000+x:08X}: {v:04x}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
