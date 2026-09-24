# -*- coding: utf-8 -*-
"""ident.py <tag> -- 从 dump 反推「每个字实际取到的是字库里哪个槽」。

做法：按 12px 相位模型，从 map+砖 重建每个字的 11x11 墨点阵；
      再在 ROM 的 1bpp 大字库(0x09500000, 16B/槽) 里做全库最近邻。
"""
import struct
import sys
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
ROM = Path(r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba").read_bytes()
BIG = 0x09500000 - 0x08000000
NSLOT = 0x2000


def slot_bits(slot, w=11, rows=11):
    b = ROM[BIG + slot * 16: BIG + (slot + 1) * 16]
    m = []
    for r in range(rows):
        row = []
        for x in range(w):
            bi = r * w + x
            row.append((b[bi >> 3] >> (7 - (bi & 7))) & 1)
        m.append(row)
    return m


tag = sys.argv[1]
v = (T / f"drive_{tag}_vram.bin").read_bytes()
io = (T / f"drive_{tag}_io.bin").read_bytes()
cbase = ((struct.unpack_from("<H", io, 0x08)[0] >> 2) & 3) * 0x4000


def pix(t):
    off = cbase + t * 32
    return [[(v[off + y * 4 + x // 2] & 0xF) if x % 2 == 0 else (v[off + y * 4 + x // 2] >> 4)
             for x in range(8)] for y in range(8)]


# 行 5 左列：map c2..c7 = 539,541,543,545,547,549 ⇒ 4 字，t0 = 539,541,545,547，相位 0,4,0,4
LAYOUT = [(539, 541, 0), (541, 543, 4), (545, 547, 0), (547, 549, 4)]
# 行 7 左列：551..562，t0 = 551,553,557,559
LAYOUT7 = [(551, 553, 0), (553, 555, 4), (557, 559, 0), (559, 561, 4)]

INK = int(sys.argv[2]) if len(sys.argv) > 2 else 1   # 行 5 的墨色 = 1


def rebuild(t0, t1, phase):
    """返回 11 列 x 11 行的「墨/非墨」，以及 11x11 的 16 行全 cell 值"""
    up0, dn0 = pix(t0), pix(t0 + 1)
    up1, dn1 = pix(t1), pix(t1 + 1)
    m = [[0] * 11 for _ in range(11)]
    for col in range(11):
        if phase == 0:
            if col < 8:
                src, j = (up0, dn0), col
            else:
                src, j = (up1, dn1), col - 8
        else:
            if col < 4:
                src, j = (up0, dn0), col + 4
            else:
                src, j = (up1, dn1), col - 4
        u, d = src
        cells = []
        for r in range(16):
            cells.append(u[r][j] if r < 8 else d[r - 8][j])
        for k in range(11):
            m[k][col] = 1 if cells[2 + k] == INK else 0
    return m


def dist(a, b):
    return sum(1 for r in range(11) for c in range(11) if a[r][c] != b[r][c])


lib = [slot_bits(s) for s in range(NSLOT)]
print("字库槽数 =", NSLOT)
for name, layout in (("行5左列", LAYOUT), ("行7左列", LAYOUT7)):
    for gi, (t0, t1, ph) in enumerate(layout):
        m = rebuild(t0, t1, ph)
        best = sorted(((dist(m, g), s) for s, g in enumerate(lib)))[:3]
        ink = sum(sum(r) for r in m)
        print("%s 字%d  t0=%d t1=%d ph=%d  墨点数=%2d  最近邻: %s"
              % (name, gi + 1, t0, t1, ph, ink,
                 "  ".join("槽%04X d=%d" % (s, d) for d, s in best)))
