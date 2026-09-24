# -*- coding: utf-8 -*-
"""原盘 vs 补丁版 设置页：tile 像素值分布（按 tilemap 调色板 bank 分组）。

要回答的问题：原盘的「红色值」与我们的「红色值」在 4bpp tile 里的
(nibble 值 -> 调色板索引) 映射是否一致；特别是**背景值**用的是 0(透明)
还是 15。
"""
import struct
import collections
import os

ROOT = r'C:/code/GBA-Rom-Translator'
VB = 0x06000000
SCR = 0x06007800
CHR = 0x06008000


def rdf(p):
    p = os.path.join(ROOT, p)
    return open(p, 'rb').read() if os.path.exists(p) else None


def report(vram, label):
    print('#' * 70)
    print('### %s' % label)
    if not vram:
        print('  !! 缺 dump')
        return
    grid = [[struct.unpack_from('<H', vram, (SCR - VB) + (r * 32 + c) * 2)[0]
             for c in range(32)] for r in range(32)]
    bynum = collections.OrderedDict()
    for r in range(32):
        for c in range(32):
            w = grid[r][c]
            n = w & 0x3FF
            if n:
                bynum.setdefault(n, (w >> 12) & 0xF)

    # 按 pal 汇总
    palv = collections.defaultdict(collections.Counter)
    paln = collections.defaultdict(set)
    for n, pal in bynum.items():
        o = (CHR - VB) + n * 32
        c = collections.Counter(vram[o:o + 32])
        palv[pal].update(c)
        paln[pal].add(n)
    print('  num_used=%d' % len(bynum))
    for pal in sorted(palv):
        tot = sum(palv[pal].values())
        vals = ' '.join('%X:%d' % (k, palv[pal][k]) for k in sorted(palv[pal]))
        print('  pal=%-2d tiles=%-4d 半字节合计=%d' % (pal, len(paln[pal]), tot))
        print('        值分布: %s' % vals)

    # 逐号紧凑打印：号 pal : 出现过的值
    print('  --- 逐号（号 pal : 值·个数）---')
    out = []
    for n, pal in sorted(bynum.items()):
        o = (CHR - VB) + n * 32
        c = collections.Counter(vram[o:o + 32])
        s = ' '.join('%X.%d' % (k, c[k]) for k in sorted(c))
        out.append('%d(p%d):%s' % (n, pal, s))
    # 每行 2 个
    for i in range(0, len(out), 2):
        print('   ' + '   |   '.join(out[i:i + 2]))


for p, lbl in [('.tmp/drive_org2_vram.bin', '原盘 设置页 (drive_org2)'),
               ('.tmp/drive_h1_vram.bin', '补丁版 v22 设置页 (drive_h1)')]:
    report(rdf(p), lbl)
