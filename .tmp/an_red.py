# -*- coding: utf-8 -*-
"""把 PALRAM + BG0 map + tile 值分布串起来：回答「红/黑到底是哪个色号」。

用法: python .tmp/an_red.py <tag> [tag2 ...]
  tag='org2' = 原盘 dump（无 pal 块则跳过调色板部分）
"""
import struct
import sys
import collections
import os

ROOT = r'C:/code/GBA-Rom-Translator'
VB = 0x06000000
SCR = 0x06007800
CHR = 0x06008000


def rd(p):
    p = os.path.join(ROOT, p)
    return open(p, 'rb').read() if os.path.exists(p) else None


def rgb555(w):
    r = w & 0x1F
    g = (w >> 5) & 0x1F
    b = (w >> 10) & 0x1F
    return '#%02X%02X%02X' % (r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2)


def main():
    for tag in (sys.argv[1:] or ['h2']):
        print('#' * 72)
        print('### tag = %s' % tag)
        vr = rd('.tmp/drive_%s_vram.bin' % tag)
        pal = rd('.tmp/drive_%s_pal.bin' % tag)
        if not vr:
            print('  !! 缺 vram dump')
            continue

        if pal:
            print('  --- BG 调色板（16 bank × 16 色）关键项 ---')
            for bank in (8, 9, 15):
                row = []
                for i in (1, 8, 15):
                    w = struct.unpack_from('<H', pal, (bank * 16 + i) * 2)[0]
                    row.append('%2d=%s' % (i, rgb555(w)))
                print('    bank %2d : %s' % (bank, '  '.join(row)))
        else:
            print('  （无 pal 块）')

        # map + 值分布
        grid = [[struct.unpack_from('<H', vr, (SCR - VB) + (r * 32 + c) * 2)[0]
                 for c in range(32)] for r in range(32)]
        bynum = collections.OrderedDict()
        for r in range(32):
            for c in range(32):
                w = grid[r][c]
                if w & 0x3FF:
                    bynum.setdefault(w & 0x3FF, (w >> 12) & 0xF)

        palsets = collections.defaultdict(set)
        for n, pal_b in bynum.items():
            o = (CHR - VB) + n * 32
            vals = set(v for v in vr[o:o + 32] for v in (v & 0xF, v >> 4))
            palsets[pal_b].add(frozenset(vals))

        print('  --- 每个调色板 bank 下，tile 像素值集合的种类 ---')
        for b in sorted(palsets):
            tiles = sum(1 for n, p in bynum.items() if p == b)
            for s in sorted(palsets[b], key=lambda s: sorted(s)):
                cnt = sum(1 for n, p in bynum.items() if p == b
                          and frozenset(v for v in vr[(CHR - VB) + n * 32:(CHR - VB) + n * 32 + 32]
                                        for v in (v & 0xF, v >> 4)) == s)
                print('    bank %2d (tiles=%-3d): 值集合 {%s}   x%d'
                      % (b, tiles, ' '.join('%X' % v for v in sorted(s)), cnt))


if __name__ == '__main__':
    main()
