# -*- coding: utf-8 -*-
"""提取 0x0806F158(win,key) 全部调用点的 key(r1)——复用已验证的 thumb_bl.scan。"""
import os
import sys
from collections import Counter

ROOT = r"C:\code\GBA-Rom-Translator"
sys.path.insert(0, os.path.join(ROOT, ".tmp"))
from thumb_bl import scan  # noqa: E402

BASE = 0x08000000
rom = open(os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba"), "rb").read()

TARGET = 0x0806F158
res = scan(rom, [TARGET])
hits = res[TARGET]
print("bl -> %08X 共 %d 处" % (TARGET, len(hits)))

keys = Counter()
for h in hits:
    off = h - BASE
    src = "?"
    key = None
    for back in range(2, 48, 2):
        ai = off - back
        if ai < 0:
            break
        ins = rom[ai] | (rom[ai + 1] << 8)
        if (ins & 0xFF00) == 0x2100:            # movs r1,#imm
            key = ins & 0xFF
            src = "imm#%d" % key
            break
        if (ins & 0xFFC0) == 0x4600 and ((ins >> 3) & 7) == 1:   # mov r1,rX
            key = "r%d" % (ins & 7)
            src = "mov r1,r%d" % (ins & 7)
            break
        if (ins & 0xF800) == 0x4800:            # ldr rX,[pc]
            key = "const"
            src = "ldr const"
            break
    print("  %08X  key=%s" % (h, src))
    if isinstance(key, int):
        keys[key] += 1

print()
print("key 直方图:", dict(sorted(keys.items())))
print("出现 key 9 或 10:", (9 in keys) or (10 in keys))
