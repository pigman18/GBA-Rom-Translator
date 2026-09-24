#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""在日版 ROM 搜索 sGlyphMasks 字节模式。
美版 text.c:251 sGlyphMasks[9][8][3]，每项 u32，小端。
特征：
  [0][0] = {FFFFFFFF,FFFFFFFF,00000000}
  [1][0] = {00000000,FFFFFFFF,FFFFFFF0}
  [8][7] = {0FFFFFFF,F0000000,00000000}
"""
import struct
ROM = r"C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba"
rom = open(ROM, "rb").read()

# 构造美版完整 sGlyphMasks
W = 9; P = 8
masks = [[[0]*3 for _ in range(P)] for _ in range(W)]
for w in range(W):
    for s in range(P):
        # 由美版规律推导：bit i (0..31) 对应像素；像素 x 落在 [s, s+w) 内则置 1
        M = 0
        for x in range(s, s + w):
            if 0 <= x < 32:
                M |= 1 << x
        # 低位禁止区 = 像素 < s ; 高位禁止区 = 像素 >= s+w
        mask1 = M                       # 允许区
        low_forbid = (1 << s) - 1       # 像素 0..s-1 禁止
        high_forbid = ((1 << 32) - 1) ^ ((1 << min(s + w, 32)) - 1)
        if s + w <= 32:
            mask2 = high_forbid
        else:
            mask2 = 0
        masks[w][s] = [mask1 & 0xFFFFFFFF, (~low_forbid) & 0xFFFFFFFF, mask2 & 0xFFFFFFFF]

# 直接验证美版明文表的前几项
print("推导表校验：")
print("  [0][0] = %08X %08X %08X   (期望 FFFFFFFF FFFFFFFF 00000000)" % tuple(masks[0][0]))
M = masks[1][0]
print("  [1][0] 推导 = %08X %08X %08X" % tuple(masks[1][0]))
print("      美版原文 = 00000000 FFFFFFFF FFFFFFF0")
print("  [8][7] 推导 = %08X %08X %08X" % tuple(masks[8][7]))
print("      美版原文 = 0FFFFFFF F0000000 00000000")
print()

def find_all(pat, label):
    hits = []
    start = 0
    while True:
        i = rom.find(pat, start)
        if i < 0: break
        hits.append(i)
        start = i + 1
    print("%-46s %d 处" % (label, len(hits)))
    for h in hits[:12]:
        print("     文件偏移 0x%06X   ROM 地址 0x%08X" % (h, 0x08000000 + h))
    return hits

# 模式 A：美版原始数组头 6 个 u32
patA = struct.pack("<6I", 0xFFFFFFFF,0xFFFFFFFF,0, 0,0xFFFFFFFF,0xFFFFFFF0)
find_all(patA, "美版 sGlyphMasks[0..1][0] 头部 (6 u32)")

# 模式 B：仅 [1][0] 三元组（很有辨识度）
patB = struct.pack("<3I", 0x00000000, 0xFFFFFFFF, 0xFFFFFFF0)
find_all(patB, "sGlyphMasks[1][0] 三元组")

# 模式 C：宽 8 行特征（每行尾随 0）
patC = struct.pack("<4I", 0x00000000,0xFFFFFFFF,0x00000000, 0x0000000F)
hitsC = find_all(patC, "width=8 前两行特征 (4 u32)")

print("\n=== 对候选做「连续 9*8*3 u32 一致性」检验 ===")
def verify(addr):
    off = addr - 0x08000000
    vals = struct.unpack_from("<%dI" % (9*8*3), rom, off)
    ok = 0
    for w in range(9):
        for s in range(8):
            for k in range(3):
                if vals[(w*8+s)*3+k] == masks[w][s][k]:
                    ok += 1
    return ok, 9*8*3

seen = set()
for h in find_all(patB, "复核 [1][0]") + find_all(patC, "复核 width8") + find_all(patA, "复核 头部"):
    if h in seen: continue
    seen.add(h)
    for base in range(max(0, h-0x60), h+8, 4):
        a = 0x08000000 + base
        ok, tot = verify(a)
        if ok > 200:
            print("  ★候选表基址 0x%08X : 匹配 %d/%d" % (a, ok, tot))
