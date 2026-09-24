# -*- coding: utf-8 -*-
"""BG0 map 逐格 + tile 内容分析（party / orgparty 对照）。
用法: python .tmp/an_map.py
"""
import struct
from pathlib import Path

D = Path(r"C:/code/GBA-Rom-Translator/.tmp")
CB = 0x4000      # BG0CNT 0x1E06 → charBase 1
SB = 30 * 0x800  # screenBase 30
R0, R1 = 0, 21
C0, C1 = 0, 30


def load(tag):
    return (D / ("drive_%s_vram.bin" % tag)).read_bytes()


def tile_nz(vr, n):
    blob = vr[CB + n * 32: CB + n * 32 + 32]
    return sum(1 for b in blob if b), blob


def dump(tag, vr, rows):
    print("=" * 78)
    print("TAG", tag)
    print("=" * 78)
    for ty in rows:
        cells = []
        for tx in range(C0, C1):
            w = struct.unpack_from("<H", vr, SB + (ty * 32 + tx) * 2)[0]
            n = w & 0x3FF
            bank = (w >> 12) & 0xF
            if n == 0:
                cells.append("     .")
            else:
                nz, _ = tile_nz(vr, n)
                cells.append("%4d%s" % (n, ("*" if nz else "!")))
        # 只打印有内容的那段
        s = "".join(cells)
        if any(c.strip() not in (".",) for c in cells):
            print("r%-2d %s" % (ty, s))


vr_p = load("party")
vr_o = load("orgparty")
dump("party(ours)", vr_p, range(R0, R1))
dump("orgparty(orig)", vr_o, range(R0, R1))

print()
print("注释: 数字=tile 号, * = tile 有非零字节, ! = tile 全 0; ' .' = 号 0")
print()
# 号使用集合对照（只看 r0..r21）
def used(vr):
    s = set()
    for ty in range(R0, R1):
        for tx in range(C0, C1):
            w = struct.unpack_from("<H", vr, SB + (ty * 32 + tx) * 2)[0]
            n = w & 0x3FF
            if n:
                s.add(n)
    return s


up, uo = used(vr_p), used(vr_o)
print("ours 用号 %d 个: %s" % (len(up), sorted(up)))
print("orig 用号 %d 个: %s" % (len(uo), sorted(uo)))
print("共有:", sorted(up & uo))
print("仅 orig 有:", sorted(uo - up))
print("仅 ours 有:", sorted(up - uo))

print()
print("--- 仅 orig 有 的号的内容（前 8 个） ---")
for n in sorted(uo - up)[:8]:
    nz, blob = tile_nz(vr_o, n)
    print("tile %-4d nz=%-3d %s | ours nz=%d" % (n, nz, blob.hex(), tile_nz(vr_p, n)[0]))

print()
print("--- ours 独占 号的内容（前 8 个） ---")
for n in sorted(up - uo)[:8]:
    nz, blob = tile_nz(vr_p, n)
    print("tile %-4d nz=%-3d %s | orig nz=%d" % (n, nz, blob.hex(), tile_nz(vr_o, n)[0]))
