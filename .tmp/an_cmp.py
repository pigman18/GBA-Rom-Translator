# -*- coding: utf-8 -*-
"""对比原盘 vs 补丁版 设置页 BG0 map 的 tile 号分配。"""
import struct, collections, os, glob

ROOT = r'C:/code/GBA-Rom-Translator'
VB = 0x06000000


def rd(p):
    p = os.path.join(ROOT, p)
    return open(p, 'rb').read() if os.path.exists(p) else None


def report(vram, base, label, lo_cut=480):
    o = base - VB
    ent = []
    for r in range(32):
        for c in range(32):
            w = struct.unpack_from('<H', vram, o + (r * 32 + c) * 2)[0]
            n = w & 0x3FF
            if n:
                ent.append((r, c, n, w))
    print('\n########## %s  BG0 @0x%08X : %d 非零格 ##########' % (label, base, len(ent)))
    by = collections.defaultdict(list)
    for r, c, n, w in ent:
        by[n].append((r, c))
    los = sorted(n for n in by if n < lo_cut)
    his = sorted(n for n in by if n >= lo_cut)
    print('低号(<%d) %d 种: %s' % (lo_cut, len(los), los))
    for n in los:
        cells = by[n]
        print('   号 %4d (x%-3d): %s' % (n, len(cells), ' '.join('(%d,%d)' % p for p in cells[:14])))
    print('高号(>=%d) %d 种: %s' % (lo_cut, len(his), his))
    for n in his:
        print('   号 %4d (x%-3d): %s' % (n, len(by[n]), ' '.join('(%d,%d)' % p for p in by[n][:14])))


for tag, path, lbl in [
    ('ORIGIN', '.tmp/drive_org2_vram.bin', '原盘 设置页'),
    ('PATCHED', '.tmp/drive_opt_vram.bin', '补丁版 设置页'),
]:
    v = rd(path)
    if not v:
        print('!! 缺 %s' % path)
        continue
    report(v, 0x06007800, lbl)
