#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
r4vram.py —— 扫全部真机 dump，算清「BG0 的瓦片号空间里，哪些号是安全的」

动机：BG 层的 screenBase 就在 VRAM 前 64KB 内浮动。若别的层把它的 tilemap
放进了本层 charBase 的窗口里，我方往那些"瓦片号"写数据就会**打烂别的层的 tilemap**。
本脚本逐 dump 算出每层 char/map 的 VRAM 字节区间，再求交。

用法: python r4vram.py            # 扫全部有 [io] 行的 dump
"""
import os, re, glob

D = r'C:\code\GBA-Rom-Translator\.tmp'
VRAM = 0x18000


def parse(tag):
    logp = os.path.join(D, 'drive_%s.log' % tag)
    try:
        log = open(logp, 'r', encoding='utf-8', errors='replace').read()
    except OSError:
        return None

    def io(name):
        m = re.search(r'\[io\] IO %s 0x[0-9a-f]+:\s*(0x[0-9a-fA-F]+)' % name, log)
        return int(m.group(1), 16) if m else None

    disp = io('DISPCNT')
    if disp is None:
        return None
    cnts = [io('BG%dCNT' % i) for i in range(4)]
    return disp, cnts


def layer_claims(disp, cnts, idx):
    """返回该层占用的 [(start, end, kind)] —— char 与 map 两块"""
    cnt = cnts[idx]
    if cnt is None:
        return []
    if not (disp >> (8 + idx)) & 1:
        return []                      # 层未启用
    cb = (cnt >> 2) & 3
    sb = (cnt >> 8) & 0x1f
    bpp8 = (cnt >> 7) & 1
    size = (disp >> 14) & 3
    out = []
    # 字符数据：整个 block 4bpp=16KB / 8bpp=32KB（保守：按层可能用满算）
    charbase = 0x4000 * cb
    out.append((charbase, charbase + 0x4000, 'char%d' % idx))
    # tilemap
    mapbytes = [0x800, 0x1000, 0x1000, 0x2000][size]
    mstart = 0x800 * sb
    out.append((mstart, mstart + mapbytes, 'map%d' % idx))
    return out


def main():
    tags = sorted({os.path.basename(p)[6:-9]
                   for p in glob.glob(os.path.join(D, 'drive_*_vram.bin'))})
    BG0_WIN = (0x8000, 0x10000)        # BG0 charBlock=2 时的瓦片号窗口
    print('BG0 charBlock=2 => 瓦片号空间 VRAM %#07x..%#07x，共 1024 瓦片'
          % BG0_WIN)
    print()
    rows = []
    for tag in tags:
        p = parse(tag)
        if not p:
            continue
        disp, cnts = p
        claims = []
        for i in range(4):
            claims += layer_claims(disp, cnts, i)
        # 只看落在 BG0 瓦片窗口内的「非本层 char」占用
        blocked = []
        for s, e, kind in claims:
            s2, e2 = max(s, BG0_WIN[0]), min(e, BG0_WIN[1])
            if s2 < e2 and kind != 'char0':
                blocked.append((s2, e2, kind))
        # 求这些占用覆盖的瓦片号
        blk_tiles = set()
        for s, e, _ in blocked:
            for t in range((s - BG0_WIN[0]) // 32, (e - BG0_WIN[0] + 31) // 32):
                blk_tiles.add(t)
        if blk_tiles:
            hi = min(blk_tiles)
            rows.append((tag, hi, sorted(blk_tiles)[:6], len(blk_tiles),
                         ['%s@%#x-%#x' % (k, s, e) for s, e, k in blocked]))
        else:
            rows.append((tag, 1024, [], 0, []))
    print('%-14s %-6s %-6s %s' % ('tag', '安全上界', '被占数', '占用详情'))
    worst = 1024
    for tag, hi, sample, n, det in rows:
        worst = min(worst, hi)
        print('%-14s %-8d %-8d %s' % (tag, hi, n, ' '.join(det) if det else '—'))
    print()
    print('全部 dump 的最小安全上界 = %d 瓦片' % worst)
    print('=> 安全池 = [521, %d)，容量 %d 瓦片' % (worst, worst - 521))


main()
