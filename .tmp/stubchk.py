# -*- coding: utf-8 -*-
"""校验成品 ROM 的三处跳转桩指向我方代码，并抽验池常量。"""
import struct

ROM = r"C:\code\GBA-Rom-Translator\roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba"
d = open(ROM, "rb").read()
BASE = 0x08000000


def u16(a):
    return struct.unpack_from("<H", d, a - BASE)[0]


def u32(a):
    return struct.unpack_from("<I", d, a - BASE)[0]


def dump(addr, n, title):
    print("--- %s @%08X ---" % (title, addr))
    out = []
    for i in range(0, n, 2):
        a = addr + i
        h = u16(a)
        out.append("%08X: %04X" % (a, h))
    print("   " + "  ".join(out))
    # 找 ldr rX, [pc, #imm] 并解出常量
    for i in range(0, n, 2):
        a = addr + i
        h = u16(a)
        if (h & 0xF800) == 0x4800:
            rt = (h >> 8) & 7
            pool = (a & ~2) + 4 + ((h & 0xFF) << 2)
            print("   @%08X ldr r%d, =0x%08X   (pool %08X)" % (a, rt, u32(pool), pool))


dump(0x080032F8, 12, "PrintNextChar 桩")
dump(0x08002C68, 12, "InitTextPrinter 桩")

# 跳板内容应与 game.bin 一致
hook = open(r"C:\code\GBA-Rom-Translator\configs\POKEMON_RUBY_AXVJ00\hook\out\game.bin", "rb").read()
same = d[0x800000:0x800000 + len(hook)] == hook
print()
print("注入区 0x08800000 与 out/game.bin 一致:", same, " len=%d" % len(hook))

# 池常量 514(0x0202)/1024(0x0400) 是否出现在代码里
import re
print("代码区含 0x0202 常量:", hook.count(struct.pack("<H", 514)))
print("代码区含 0x0400 常量:", hook.count(struct.pack("<H", 1024)))
