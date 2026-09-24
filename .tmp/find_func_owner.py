# -*- coding: utf-8 -*-
"""对给定调用点，向上回溯找函数入口（push 指令 + 前一条是 bx/pop/b 的边界）。"""
import struct
rom = open('work/POKEMON_RUBY_AXVJ00/build/baserom.gba','rb').read()
BASE = 0x08000000
def u16(a): return struct.unpack_from('<H', rom, a-BASE)[0]

def is_prologue(a):
    hw = u16(a)
    # push {..., lr}  0xB5xx
    if (hw & 0xFF00) == 0xB500: return True
    # push {..., r7, lr}? 0xB5xx 已含
    return False

def is_end(a):
    hw = u16(a)
    if (hw & 0xFF87) == 0x4700: return True   # bx rX
    if (hw & 0xF800) == 0xE000: 
        c = (hw>>8)&0xF
        return c in (0xE, 0xF, 0x1, 0xD)      # b / svc / beq...bgt
    if (hw & 0xFE00) == 0xBC00: return True   # pop
    return False

def owner(site):
    a = site - 2
    lim = site - 0x400
    while a > lim:
        hw = u16(a)
        # mvn/lsls 填充不算
        if is_prologue(a):
            # 检查前面是否结束
            if is_end(a-2) or a == site-2:
                return a
            # 允许 4 字节对齐填充 0000
            if u16(a-2) == 0x0000:
                return a
        a -= 2
    return None

sites = [0x08002AA6,0x08002B16,0x080033A2,0x08003542,   # DGT 调用点
         0x08002AC0,0x08002B44,0x08002BB4,0x08002C00,0x08002D70,0x08002D8A,0x08003420,0x08003430,0x0800369C,0x080036AA,
         0x08002AE4,0x08002B7E,0x08003440,0x08003452,0x080036BA,0x080036CA,
         0x080033E4,0x08003660]
for s in sorted(sites):
    o = owner(s)
    print('%08X -> owner %s' % (s, ('%08X'%o) if o else '???'))
