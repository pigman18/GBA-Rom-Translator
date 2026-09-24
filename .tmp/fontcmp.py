# -*- coding: utf-8 -*-
"""fontcmp.py <tag> <bg> <slot> [slot2 ...] — 用 ROM 里的 1bpp 小库真值，
   逐像素对拍「从 VRAM 重建出来的整字」。

   小库: ADDR 0x09600000（ROM 偏移 0x1600000），11 B/字，ink 9×9 @ 行偏移 5。
   cell 预期值: 字形 1 → color_c(15)；字形 0 但左上邻为 1 → color_e；否则 color_d。
"""
import sys
import struct
from pathlib import Path

T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
ROM = Path(r"C:/code/GBA-Rom-Translator/roms/outputs/_t1.gba")
tag, bg = sys.argv[1], sys.argv[2]
want = [int(x) for x in sys.argv[3:]]
LAYER = {"0": (30, 1), "2": (15, 2)}
sb, cb = LAYER[bg]
BASE, STRIDE, BGK = 352, 4, 0x8

vram = (T / ("drive_%s_vram.bin" % tag)).read_bytes()
ew = (T / ("drive_%s_ewram.bin" % tag)).read_bytes()
rom = ROM.read_bytes()
SMALL_OFF = 0x1600000


def tile(n):
    return vram[cb * 0x4000 + n * 32: cb * 0x4000 + n * 32 + 32]


def px(t, x, y):
    return (t[y * 4 + (x >> 1)] >> ((x & 1) * 4)) & 0xF


def font_mask(code, w=9, rows=9, stride=11):
    """1bpp 位流 → 9×9 的 0/1 矩阵（每行 w 位 MSB-first，行间无填充）。"""
    d = rom[SMALL_OFF + code * stride: SMALL_OFF + code * stride + stride]
    m = [[0] * w for _ in range(rows)]
    for r in range(rows):
        for x in range(w):
            bi = r * w + x
            m[r][x] = (d[bi >> 3] >> (7 - (bi & 7))) & 1
    return m


def expected_cell(code, rowoff=5, cc=15, ce=1, cd=0):
    m = font_mask(code)
    cell = [[cd] * 9 for _ in range(16)]
    for r in range(9):
        for x in range(9):
            if m[r][x]:
                cell[rowoff + r][x] = cc
            elif r >= 1 and x >= 1 and m[r - 1][x - 1]:
                cell[rowoff + r][x] = ce
    return cell


ok_all = True
for slot in want:
    lo, hi = struct.unpack_from("<II", ew, 0x3E000 + BGK + slot * 8)
    code, ink, phase = (lo >> 3) >> 8, (lo >> 3) & 0xF, lo & 7
    tl = BASE + slot * STRIDE
    w0 = min(8 - phase, ink)
    w1 = ink - w0
    L, R = tile(tl), tile(tl + 2)
    got = [[None] * ink for _ in range(16)]
    for y in range(8):
        for x in range(w0):
            got[y][phase + x] = px(L, x, y)
        for x in range(w1):
            got[y + 8][x] = px(R, x, y)
    exp = expected_cell(code)
    bad = [(x, y, got[y][x], exp[y][x]) for y in range(16) for x in range(ink)
           if got[y][x] != exp[y][x]]
    print("slot%-3d code=%03X phase=%d  重建整字 vs 字库真值: %s"
          % (slot, code, phase,
             "完全一致 OK" if not bad else "差异 %d 处 %s" % (len(bad), bad[:10])))
    if bad:
        ok_all = False
        print("   --- 实际 ---")
        for y in range(16):
            print("   %2d %s" % (y, "".join("%X" % v if v is not None else "?" for v in got[y])))
        print("   --- 真值 ---")
        for y in range(16):
            print("   %2d %s" % (y, "".join("%X" % v for v in exp[y])))

print("\n==== %s ====" % ("全部与字库真值一致" if ok_all else "存在差异"))
