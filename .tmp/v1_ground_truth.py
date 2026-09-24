#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一次性脚本：建立 0x08003000-0x08004000 区域的函数边界与跳转表指纹。
只做静态分析。
"""
import struct, sys, os

ROM = r"C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba"
rom = open(ROM, "rb").read()
print("ROM size = %d bytes (%.1f MB)" % (len(rom), len(rom)/1024/1024))
print("注意：卡带映射时 0x08000000+off，off 最大 = %X\n" % (len(rom)-1))

def u16(a):
    o = a - 0x08000000
    return struct.unpack_from("<H", rom, o)[0]

def u32(a):
    o = a - 0x08000000
    return struct.unpack_from("<I", rom, o)[0]

# 已知锚点扫描：找 push {...,lr} 函数入口 + bx lr 结束
print("=== 0x08003600-0x08003A00 函数入口候选 (push {r4,r5,r6,r7,lr} / push {r4,lr} ...) ===")
POPS = {0xb5f0, 0xb5f8, 0xb5f0, 0xb510, 0xb570, 0xb580, 0xb5b0, 0xb5e0, 0xb538}
for a in range(0x08003600, 0x08003A00, 2):
    v = u16(a)
    if v in (0xb5f0, 0xb510, 0xb570, 0xb580, 0xb5e0, 0xb538, 0xb5f8):
        # 检查前一条是不是 bx lr / pop {pc} / b (返回到此 & 上一函数结束)
        prev = u16(a - 2)
        tail = "?"
        if prev == 0x4770: tail = "bx lr"
        elif (prev & 0xff00) == 0xbd00: tail = "pop {...,pc}"
        elif prev == 0x46c0: tail = "nop(pad)"
        print("  0x%08X: %04x  push  (prev=%04x %s)" % (a, v, prev, tail))

print("\n=== 跳转表定位（找 'ldr rX,[pc,#n]' + 'add rX,rX,rX' + 'mov pc,rX' 模式）===")
# ldr rD,[pc,#imm]  = 01001 rD imm8 ; adds rD,rD,rD = 0001100 rD rD ; mov pc,rD = 01000111 1000 rD 00
for a in range(0x08003600, 0x08003A00, 2):
    v = u16(a)
    # ldr rD,[pc,#imm]: bits 15-11 = 01001
    if (v >> 11) == 0b01001:
        rd = (v >> 8) & 7
        imm = (v & 0xFF) * 4
        lit = a + 4 + imm
        lw = u16(a + 2)
        # adds rD, rD, rD : 0001 100 rD rD
        if lw == (0x1800 | (rd << 6 | rd << 3 | rd)):
            l3 = u16(a + 4)
            if l3 == (0x4697 if rd == 7 else 0x4687 | 0):
                pass
        # mov pc, rD = 0x4687 | (rd<<3)
        if l3s := u16(a + 4):
            if l3s == (0x4687 | (rd << 3)):
                print("  表@0x%08X (指令@0x%08X): ldr r%d,[pc,#%d] -> table ptr = 0x%08X"
                      % (lit, a, rd, imm, u32(lit)))
                if 0x08000000 <= u32(lit) < 0x08000000 + len(rom):
                    tb = u32(lit)
                    ents = []
                    for k in range(8):
                        e = u32(tb + 4 * k)
                        ents.append("0x%08X" % e)
                        if not (0x08000000 <= e < 0x08000000 + len(rom)):
                            break
                    print("       entries: %s" % ", ".join(ents))
