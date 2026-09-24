# -*- coding: utf-8 -*-
"""静态核对 53 条窗口模板的 (textMode, font, charBase) 分布。
字段偏移（0x08002878 逐指令实证）：
  +0x00 bgId  +0x01 charBase  +0x02 screenBase  +0x03 prio
  +0x08 font  +0x09 textMode  +0x0C tileData    +0x10 tilemap
表基址 0x081BB3DC，步长 0x18，共 53 条。
"""
import struct

ROM = r"C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba"
data = open(ROM, "rb").read()

BASE = 0x081BB3DC
N = 53
STRIDE = 0x18
VRAM = 0x06000000


def off(addr):
    return addr - 0x08000000


rows = []
for i in range(N):
    o = off(BASE + i * STRIDE)
    bg, cb, sb, prio, font, tm = (data[o + 0], data[o + 1], data[o + 2],
                                  data[o + 3], data[o + 8], data[o + 9])
    td = struct.unpack_from("<I", data, o + 0x0C)[0]
    mp = struct.unpack_from("<I", data, o + 0x10)[0]
    rows.append((i, bg, cb, sb, prio, font, tm, td, mp))

print("idx  bg cb sb  fo tm  tileData   tilemap    nextBlk")
print("-" * 66)
from collections import Counter
c_tm = Counter()
c_cb_tm1 = Counter()
for (i, bg, cb, sb, prio, font, tm, td, mp) in rows:
    c_tm[tm] += 1
    nb = (VRAM + (cb + 1) * 0x4000) if cb < 3 else None
    nbs = ("%08X" % nb) if nb else "**越界(OBJ)**"
    print("%3d  %d  %d  %2d  %d  %d  %08X  %08X  %s"
          % (i, bg, cb, sb, font, tm, td, mp, nbs))
    if tm == 1:
        c_cb_tm1[cb] += 1

print()
print("textMode 分布:", dict(sorted(c_tm.items())))
print("charBase 分布(全部):", dict(sorted(Counter(r[2] for r in rows).items())))
print("charBase 分布(tm1 文本层):", dict(sorted(c_cb_tm1.items())))
print()
print("=== tm1 且 charBase=3（我方池会踩 OBJ 区）===")
for r in rows:
    if r[6] == 1 and r[2] == 3:
        print("  idx=%d bg=%d td=%08X mp=%08X" % (r[0], r[1], r[7], r[8]))
