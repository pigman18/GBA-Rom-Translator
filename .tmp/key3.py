# -*- coding: utf-8 -*-
"""解析 0x0806F158(win,key) 调用点的 key：支持 movs / mov / ldr=const（解常量池）。"""
import os
import struct
import sys
from collections import Counter

ROOT = r"C:\code\GBA-Rom-Translator"
sys.path.insert(0, os.path.join(ROOT, ".tmp"))
from thumb_bl import scan  # noqa: E402

BASE = 0x08000000
rom = open(os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba"), "rb").read()
TARGET = 0x0806F158
hits = scan(rom, [TARGET])[TARGET]
print("bl -> %08X 共 %d 处" % (TARGET, len(hits)))

keys = Counter()
detail = []
for h in hits:
    off = h - BASE
    key = None
    src = "?"
    for back in range(2, 48, 2):
        ai = off - back
        if ai < 0:
            break
        ins = rom[ai] | (rom[ai + 1] << 8)
        if (ins & 0xFF00) == 0x2100:
            key = ins & 0xFF
            src = "imm#%d" % key
            break
        if (ins & 0xFFC0) == 0x4600 and ((ins >> 3) & 7) == 1:
            key = "r%d" % (ins & 7)
            src = "mov r1,r%d" % (ins & 7)
            break
        if (ins & 0xF800) == 0x4800:            # ldr rX,[pc,#imm]  -> 读常量池
            rt = (ins >> 8) & 7
            paddr = (h - back) & ~2
            pool = paddr + 4 + ((ins & 0xFF) << 2)
            if not (BASE <= pool < BASE + len(rom) - 4):
                src = "const越界"
                continue
            v = struct.unpack_from("<I", rom, pool - BASE)[0]
            if rt == 1:
                key = v
                src = "const#%d(0x%X)" % (v, v)
                break
            else:
                src = "ldr r%d=const(非r1)" % rt
                continue
    detail.append((h, src))
    if isinstance(key, int):
        keys[key] += 1

for h, s in detail:
    print("  %08X  %s" % (h, s))
print()
print("key 直方图:", dict(sorted(keys.items())))
print("出现 key 9 或 10:", (9 in keys) or (10 in keys))

# 模板指针是否被代码直接引用（绕过注册表）
print()
for ptr in (0x081BB514, 0x081BB52C):
    pat = struct.pack("<I", ptr)
    n = rom.count(pat)
    print("tpl %08X 在 ROM 中出现 %d 次（注册表各 1 次）" % (ptr, n))
