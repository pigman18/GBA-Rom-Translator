#!/usr/bin/env python3
"""BL 调用点扫描 —— Thumb BL (T1) 正确解码。

Thumb-2 BL (32-bit)：
  F1: 11110 S imm10          (hw1: bits 15-11 = 11110)
  F2: 11 J1 1 imm11          (hw2: bits 15-14 = 11, bit13 = J1, bit12 = 1)
  I1 = ~(J1 ^ S) & 1
  I2 = ~(J2 ^ S) & 1
  imm32 = SignExtend(S:I1:I2:imm10:imm11:0)
  目标 = 当前指令地址 + 4 + imm32

★ 之前血案：把 hw2 的判据写成 (hw2>>11)==0b11111，
  这只匹配 J1=1，漏掉 J1=0 的一半 ⇒ 扫出 0 处。
  正确判据： (hw1>>11)==0b11110 and (hw2>>14)==0b11 and ((hw2>>12)&1)==1
"""
from __future__ import annotations

import os
import struct
import sys

ROOT = r"C:\code\GBA-Rom-Translator"
ROM_PATH = os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba")

TARGETS = {
    0x08003630: "DrawGlyphTiles",
    0x08003830: "DrawGlyphTile_Unshadowed",
    0x080038A0: "DrawGlyphTile_Shadowed",
    0x08002A50: "InitWindowTileData",
    0x08003708: "GetCursorTileNum",
    0x08003730: "GetGlyphTilePointers",
    0x080029E0: "MultistepLoadFont",
    0x08002950: "?font1",           # ①
    0x080041BC: "GetBlankTileNum",
}


def bl_target(rom: bytes, off: int):
    hw1 = struct.unpack_from("<H", rom, off)[0]
    hw2 = struct.unpack_from("<H", rom, off + 2)[0]
    if (hw1 >> 11) != 0b11110:
        return None
    if (hw2 >> 14) != 0b11:
        return None
    if ((hw2 >> 12) & 1) != 1:
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
    # ★ pc = 0x08000000 + off（off 是文件偏移 = ROM 地址的低 24 位）
    return (0x08000000 + off + 4 + imm) & 0xFFFFFFFF


def main() -> int:
    rom = open(ROM_PATH, "rb").read()
    print(f"ROM {len(rom)} bytes")
    found = {k: [] for k in TARGETS}
    total = 0
    for off in range(0, len(rom) - 4, 2):
        t = bl_target(rom, off)
        if t is None:
            continue
        total += 1
        if t in found:
            found[t].append(0x08000000 + off)
    print(f"全 ROM 共解出 {total} 条 BL\n")
    for k, name in TARGETS.items():
        lst = found[k]
        print(f"{name} (0x{k:08X})  <- {len(lst)} 处")
        for a in lst:
            print(f"    0x{a:08X}")
    # 反向：把 0x08003630 的调用点反汇编上下文
    print("\n=== 4 个 DrawGlyphTiles 调用点上下文 ===")
    for a in found[0x08003630]:
        off = a - 0x08000000
        lo = max(0, off - 16)
        print(f"\n--- 调用点 0x{a:08X} ---")
        for x in range(lo, off + 12, 2):
            v = struct.unpack_from("<H", rom, x)[0]
            mark = "  <== BL DrawGlyphTiles" if x == off else ""
            print(f"  0x{0x08000000 + x:08X}: {v:04x}{mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
