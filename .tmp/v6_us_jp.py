#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""在美版 Ruby ROM 中定位真正的 sGlyphMasks，再回到日版比对。"""
import struct, os, glob
ROOT = r"C:\code\GBA-Rom-Translator"
us_path = os.path.join(ROOT, "roms", "origin", "Pokemon Ruby Version 1.1(US).gba")
jp_path = os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba")
us = open(us_path, "rb").read()
jp = open(jp_path, "rb").read()
print("US %d bytes  JP %d bytes" % (len(us), len(jp)))

# 美版精确表（手抄自 tools/pokeruby/src/text.c:251）
src = open(os.path.join(ROOT,"tools","pokeruby","src","text.c"), "rb").read().decode("utf-8","replace")
i0 = src.index("static const u32 sGlyphMasks")
i1 = src.index("};", i0)
body = src[i0:i1]
import re
vals = [int(x,16) for x in re.findall(r"0x([0-9A-Fa-f]{8})", body)]
print("从 text.c 提取 sGlyphMasks 常量个数 = %d  (期望 %d)" % (len(vals), 9*8*3))
pat = struct.pack("<%dI" % len(vals), *vals)

print("\n=== 在美版 ROM 搜索该模式 ===")
hits_us = []
s = 0
while True:
    i = us.find(pat, s)
    if i < 0: break
    hits_us.append(i); s = i+1
print("  命中 %d 处: %s" % (len(hits_us), ["0x%08X"%(0x08000000+h) for h in hits_us]))

print("\n=== 在日版 ROM 搜索该模式 ===")
hits_jp = []
s = 0
while True:
    i = jp.find(pat, s)
    if i < 0: break
    hits_jp.append(i); s = i+1
print("  命中 %d 处: %s" % (len(hits_jp), ["0x%08X"%(0x08000000+h) for h in hits_jp]))

# 用美版表的前 1/2/4/8/16 项逐步放宽搜索
print("\n=== 逐步放宽前缀长度，看日版匹配到哪一步 ===")
for n in (1,2,3,4,5,6,8,12,16,24,32,48,72,108,216):
    p = struct.pack("<%dI"%n, *vals[:n])
    cj = jp.count(p); cu = us.count(p)
    print("  前 %3d 个 u32: US %d 处, JP %d 处" % (n, cu, cj))

if hits_us:
    base = hits_us[0]
    print("\n=== 美版表内容确认 (0x%08X) ===" % (0x08000000+base))
    for k in range(0, 216, 8):
        row = struct.unpack_from("<8I", us, base+k)
        print("  +%03X: %s" % (k, " ".join("%08X"%v for v in row)))
