#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
r4vram2.py —— 精确求「BG0 charBlock=2 的瓦片号窗口 (VRAM 0x8000..0xC000, 号 0..511)」
             与「窗口 0xC000..0x10000, 号 512..1023」里，到底哪些瓦片被别的东西占着。

判据（精确，不保守）：
  1) 任何层 i 的 **tilemap 字节** 落进窗口 -> 对应瓦片被占（这是原始地图数据，写了必坏）
  2) 任何层 i 的 **charBase == 2 或 3** -> 它的地图里引用的每个瓦片号
     都物理落在本窗口内（因为 tile n = charBase + 32n）-> 被占
  3) 8bpp 层的瓦片占 64 字节（跨两个 4bpp 号）

用法: python r4vram2.py [只跑某 tag]
"""
import os, re, glob, sys

D = r'C:\code\GBA-Rom-Translator\.tmp'
WIN = (0x8000, 0x10000)          # 我们关心的物理窗口（BG0 charBlock=2）


def parse(tag):
    logp = os.path.join(D, 'drive_%s.log' % tag)
    vramp = os.path.join(D, 'drive_%s_vram.bin' % tag)
    if not (os.path.exists(logp) and os.path.exists(vramp)):
        return None
    log = open(logp, 'r', encoding='utf-8', errors='replace').read()
    vram = open(vramp, 'rb').read()

    def io(name):
        m = re.search(r'\[io\] IO %s 0x[0-9a-f]+:\s*(0x[0-9a-fA-F]+)' % name, log)
        return int(m.group(1), 16) if m else None

    disp = io('DISPCNT')
    cnts = [io('BG%dCNT' % i) for i in range(4)]
    if disp is None:
        return None
    return disp, cnts, vram


def layer(tag, disp, cnt, idx, vram):
    """返回 (占用瓦片号集合(相对0x8000), 说明)"""
    if cnt is None or not (disp >> (8 + idx)) & 1:
        return set(), []
    cb = (cnt >> 2) & 3
    sb = (cnt >> 8) & 0x1f
    bpp8 = (cnt >> 7) & 1
    size = (cnt >> 14) & 3
    MW = [32, 64, 32, 64][size]
    MH = [32, 32, 64, 64][size]
    tilesz = 64 if bpp8 else 32
    tilemask = 0x1ff if bpp8 else 0x3ff

    base = 0x4000 * cb
    mstart = 0x800 * sb
    mbytes = MW * MH * 2

    occ = set()
    notes = []

    # (1) tilemap 本身落进窗口
    s, e = max(mstart, WIN[0]), min(mstart + mbytes, WIN[1])
    if s < e:
        for t in range((s - WIN[0]) // 32, (e - WIN[0] + 31) // 32):
            occ.add(t)
        notes.append('MAP%s' % idx)

    # (2) 该层字符基址落进窗口（含跨窗口）
    if base < WIN[1] and base + 0x4000 > WIN[0]:
        nref = 0
        for r in range(MH):
            for c in range(MW):
                off = mstart + (r * MW + c) * 2
                if off + 2 > len(vram):
                    continue
                ent = vram[off] | (vram[off + 1] << 8)
                tn = ent & tilemask
                phys = base + tilesz * tn
                ps, pe = phys, phys + tilesz
                if ps < WIN[1] and pe > WIN[0]:
                    a = max(ps, WIN[0])
                    b = min(pe, WIN[1])
                    for t in range((a - WIN[0]) // 32, (b - WIN[0] + 31) // 32):
                        occ.add(t)
                    nref += 1
        notes.append('CHAR%s(cb%d,引%d格)' % (idx, cb, nref))
    return occ, notes


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    tags = sorted({os.path.basename(p)[6:-9]
                   for p in glob.glob(os.path.join(D, 'drive_*_vram.bin'))})
    print('窗口 = BG0 charBlock2 => VRAM %#07x..%#07x（瓦片号 0..1023）' % WIN)
    print()
    print('%-12s %-8s %-8s %s' % ('tag', '521自由?', '最大空段', '占用瓦片号(相对窗口)'))
    agg_free = None
    for tag in tags:
        if only and tag != only:
            continue
        p = parse(tag)
        if not p:
            continue
        disp, cnts, vram = p
        occ = set()
        notes = []
        for i in range(4):
            o, n = layer(tag, disp, cnts[i], i, vram)
            occ |= o
            notes += n
        # 求从 521 起的最大连续空段
        t = 521
        while t < 1024 and t not in occ:
            t += 1
        run = t - 521
        hi = sorted(x for x in occ if x >= 521)
        lo = sorted(x for x in occ if x < 521)
        print('%-12s %-8s %-8d 521上界=%s  <521占用=%d个%s'
              % (tag, 'YES' if run >= 8 else 'NO', run,
                 ('%d' % hi[0]) if hi else '1024',
                 len(lo), (' 示例%s' % lo[:8]) if lo else ''))
        if agg_free is None or run < agg_free:
            agg_free = run
    print()
    print('所有 dump 里「从 521 起的最短连续空段」= %d 瓦片' % agg_free)
    print('=> 可无条件安全使用的池 = [521, %d)' % (521 + agg_free))


main()
