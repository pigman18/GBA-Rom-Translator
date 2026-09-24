#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""建立函数边界：以 push{...,lr} 入口 + 其后所有 bx lr / pop pc 结束点划分。"""
import struct

ROM = r"C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba"
rom = open(ROM, "rb").read()

def u16(a):
    return struct.unpack_from("<H", rom, a - 0x08000000)[0]

def u32(a):
    return struct.unpack_from("<I", rom, a - 0x08000000)[0]

def is_push(hw):
    return (hw & 0xFE00) == 0xB400 and ((hw >> 8) & 1) == 1  # push {..., lr}

# 收集候选入口
entries = []
for a in range(0x08003600, 0x08003B00, 2):
    if is_push(u16(a)):
        entries.append(a)

targets = [0x08003630, 0x080033B4, 0x080036DC, 0x08003708, 0x08003730,
           0x08003830, 0x080038A0, 0x08002A50]
print("=== 目标地址落在哪个函数体内 ===")
for t in targets:
    owner = None
    for e in entries:
        if e <= t:
            owner = e
    print("  0x%08X  -> 所属入口 0x%08X   %s"
          % (t, owner, "★是入口" if owner == t else "(体内部偏移 +0x%X)" % (t - owner)))

print("\n=== 0x08003600-0x08003B00 全部 push 入口 ===")
for e in entries:
    print("  0x%08X  hw=%04x" % (e, u16(e)))

print("\n=== 逐地址扫描 mov pc,rX 跳转 (0x4687|rd<<3) ===")
for a in range(0x08003600, 0x08003B00, 2):
    hw = u16(a)
    if (hw & 0xFF87) == 0x4687:
        rd = (hw >> 3) & 7
        print("  mov pc, r%d @0x%08X" % (rd, a))
        # 往回找 ldr rD,[pc,#imm] 和 adds rD,rD,rD
        for back in range(2, 10, 2):
            p1 = u16(a - back)
            p2 = u16(a - back + 2)
            if (p2 & 0xFE00) == 0x1800:  # adds
                pass
            if (p1 >> 11) == 0b01001:
                dd = (p1 >> 8) & 7
                imm = (p1 & 0xFF) * 4
                lit = a - back + 4 + imm
                tb = u32(lit)
                print("     ldr r%d,[pc] @0x%08X  table=0x%08X" % (dd, a - back, tb))
                if 0x08000000 <= tb < 0x08000000 + len(rom):
                    for k in range(8):
                        e = u32(tb + 4 * k)
                        ok = 0x08000000 <= e < 0x08000000 + len(rom)
                        print("       [%d]=0x%08X %s" % (k, e, "" if ok else "<OUT>"))
                        if not ok:
                            break
                break
