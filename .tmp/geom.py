# -*- coding: utf-8 -*-
"""geom.py <tag> <lo> <ncol> <ink> -- 暴力搜「真实 12px 几何」：
把 lo 起 ncol 个 map 列拼成像素带（16 行高），按 (x0, advance) 切字，
在每个候选下算「与字库全库最近邻距离之和」，取最优。距离≈0 的候选就是真几何。
"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
ROM = Path(r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()
BIG = 0x09500000 - 0x08000000
NS = 0x2000


def slot_bits(s):
    b = ROM[BIG + s * 16: BIG + (s + 1) * 16]
    return tuple((b[(r * 11 + x) >> 3] >> (7 - ((r * 11 + x) & 7))) & 1
                 for r in range(11) for x in range(11))


LIB = [slot_bits(s) for s in range(NS)]

tag, lo, ncol, ink = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
v = (T / f"drive_{tag}_vram.bin").read_bytes()
io = (T / f"drive_{tag}_io.bin").read_bytes()
cbase = ((struct.unpack_from("<H", io, 0x08)[0] >> 2) & 3) * 0x4000

# 像素带：宽 = ncol*8, 高 = 16
W = ncol * 8
band = [[0] * W for _ in range(16)]
for c in range(ncol):
    for half in (0, 1):
        t = lo + 2 * c + half
        off = cbase + t * 32
        for y in range(8):
            for x in range(8):
                b = v[off + y * 4 + x // 2]
                band[half * 8 + y][c * 8 + x] = (b & 0xF) if x % 2 == 0 else (b >> 4)

print("== 像素带（'#'=墨%d ':'=阴影8 '.'=底15 '?'=其他） ==" % ink)
for r in range(16):
    print("   " + "".join("#" if q == ink else ":" if q == 8 else "." if q == 15
                          else "?" if q == 0 else "%X" % q for q in band[r]))


def extract(x0, adv, k):
    """第 k 个字的 11x11 墨点（行取 2..12）"""
    xs = x0 + k * adv
    if xs < 0 or xs + 11 > W:
        return None
    m = []
    for r in range(11):
        m.append([1 if band[2 + r][xs + c] == ink else 0 for c in range(11)])
    return tuple(q for row in m for q in row)


best = []
for adv in range(8, 17):
    for x0 in range(0, adv):
        glyphs = [extract(x0, adv, k) for k in range(3)]
        if any(g is None for g in glyphs):
            continue
        tot, ds = 0, []
        for g in glyphs:
            d, s = min((sum(1 for a, b in zip(g, lib) if a != b), i)
                       for i, lib in enumerate(LIB))
            tot += d
            ds.append((d, s))
        best.append((tot, adv, x0, ds))
best.sort()
print("\n== (advance, x0) 搜索：3 字距离和最小 ==")
for tot, adv, x0, ds in best[:10]:
    print("  adv=%2d x0=%2d  总距=%3d  %s" % (adv, x0, tot,
          "  ".join("d=%d 槽%04X" % (d, s) for d, s in ds)))
