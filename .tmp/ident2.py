# -*- coding: utf-8 -*-
"""ident2.py <tag> <lo> <ncol> -- 从周期块前 ncol 个 map 列（墨色=1 的干净列）重建字并全库最近邻。"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
ROM = Path(r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()
BIG = 0x09500000 - 0x08000000


def slot_bits(slot, w=11, rows=11):
    b = ROM[BIG + slot * 16: BIG + (slot + 1) * 16]
    return [[(b[(r * w + x) >> 3] >> (7 - ((r * w + x) & 7))) & 1 for x in range(w)]
            for r in range(rows)]


tag = sys.argv[1]
lo = int(sys.argv[2])
ncol = int(sys.argv[3])
v = (T / f"drive_{tag}_vram.bin").read_bytes()
io = (T / f"drive_{tag}_io.bin").read_bytes()
cbase = ((struct.unpack_from("<H", io, 0x08)[0] >> 2) & 3) * 0x4000
byh = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0   # 竖排缩放（16 行 -> 行位置）


def pix(t):
    off = cbase + t * 32
    return [[(v[off + y * 4 + x // 2] & 0xF) if x % 2 == 0 else (v[off + y * 4 + x // 2] >> 4)
             for x in range(8)] for y in range(8)]


# 周期块的第 c 个 map 列 => 上砖 lo+2c, 下砖 lo+2c+1
cols = {}
for c in range(ncol):
    t = lo + 2 * c
    cols[c] = (pix(t), pix(t + 1))

# 该段里的字：相位 0 -> 列 0..7 出自列c, 列8..10 出自列c+1（偏移0）
#             相位 4 -> 列 0..3 出自列c 的偏移 4..7, 列4..10 出自列c+1 偏移 0..6
for gi, (c0, ph) in enumerate([(0, 0), (1, 4)]):
    u0, d0 = cols[c0]
    u1, d1 = cols[c0 + 1]
    m = [[0] * 11 for _ in range(11)]
    for col in range(11):
        if ph == 0:
            if col < 8:
                u, d, j = u0, d0, col
            else:
                u, d, j = u1, d1, col - 8
        else:
            if col < 4:
                u, d, j = u0, d0, col + 4
            else:
                u, d, j = u1, d1, col - 4
        rows16 = [u[r][j] for r in range(8)] + [d[r][j] for r in range(8)]
        for k in range(11):
            m[k][col] = 1 if rows16[2 + k] == 1 else 0
    best = sorted(((sum(1 for r in range(11) for cc in range(11) if m[r][cc] != g[r][cc]), s)
                   for s, g in enumerate(
                       (slot_bits(s) for s in range(0x2000)))))[:4]
    print("列%d 起 字%d ph=%d 墨点=%2d 最近邻: %s"
          % (c0, gi + 1, ph, sum(sum(r) for r in m),
             "  ".join("槽%04X d=%d" % (s, d) for d, s in best)))
    for r in m:
        print("     " + "".join("#" if q else "." for q in r))
