# -*- coding: utf-8 -*-
"""v22 方案 H 的 L2 判据：直接从 VRAM dump 里判「块间是否还共用号」。

用法：
    python .tmp/an_h.py <tag>            # 读 .tmp/drive_<tag>_vram.bin

输出：
  ① BG0 map（screenBase 由 BG0CNT 推）的号分布，按"块"分组打印
  ② 每个被引用的 tile 的 4bpp 位图（ASCII）—— 一眼看出字形是否完整、是否重复
  ③ 号统计：distinct 数 / 是否还有"多块共用同一号"
"""
import struct
import sys
import collections
import os

VRAM_BASE = 0x06000000


def load(tag):
    vr = open('.tmp/drive_%s_vram.bin' % tag, 'rb').read()
    io = open('.tmp/drive_%s_io.bin' % tag, 'rb').read() if os.path.exists(
        '.tmp/drive_%s_io.bin' % tag) else b''
    return vr, io


def bg0cnt(io):
    if len(io) >= 2:
        return struct.unpack_from('<H', io, 0)[0]
    return None


def tile_bits(vr, char_base_addr, tnum):
    """8×8 4bpp tile → 8 行，每行 8 个 0..15。"""
    o = char_base_addr - VRAM_BASE + tnum * 32
    rows = []
    for r in range(8):
        word = struct.unpack_from('<I', vr, o + r * 4)[0]
        rows.append([(word >> (4 * c)) & 0xF for c in range(8)])
    return rows


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else 'opt'
    vr, io = load(tag)
    cnt = bg0cnt(io)
    if cnt is None:
        print('!! 没有 io dump，默认 screenBase=15 / charBase=2')
        scr, chb = 15, 2
    else:
        scr = (cnt >> 8) & 0x1F
        chb = (cnt >> 2) & 0x3
        print('BG0CNT = 0x%04X  ⇒ screenBase=%d(0x%08X)  charBase=%d(0x%08X)  4bpp'
              % (cnt, scr, VRAM_BASE + scr * 0x800, chb, VRAM_BASE + chb * 0x4000))
    map_addr = VRAM_BASE + scr * 0x800
    char_addr = VRAM_BASE + chb * 0x4000
    mo = map_addr - VRAM_BASE

    # ---- 读 map ----
    grid = []
    for r in range(32):
        row = [struct.unpack_from('<H', vr, mo + (r * 32 + c) * 2)[0] for c in range(32)]
        grid.append(row)

    print()
    print('=== 号分布（只打印非零行；号 = tile 号 10 位）===')
    print('      ' + ''.join('%4d' % c for c in range(30)))
    for r in range(20):
        nums = [grid[r][c] & 0x3FF for c in range(30)]
        if any(nums):
            print('%4d  %s' % (r, ''.join('%4d' % v for v in nums)))

    # ---- 统计 ----
    used = collections.Counter()
    for r in range(32):
        for c in range(32):
            v = grid[r][c] & 0x3FF
            if v:
                used[v] += 1
    print()
    print('=== 号统计 ===')
    print('  被引用的不同 tile 号 = %d 个' % len(used))
    print('  号区间 = [%d .. %d]' % (min(used), max(used)))
    lo = sorted(k for k in used if k < 600)
    print('  <600 的号: %s' % lo[:80])

    # ---- 每个号的字形位图 ----
    print()
    print('=== 被引用的 tile 位图（上/下半成对打印：号 n = 上半，n+1 = 下半）===')
    printed = set()
    for n in sorted(used):
        if n in printed:
            continue
        printed.add(n)
        printed.add(n + 1)
        for half, tn in (('上', n), ('下', n + 1)):
            if tn * 32 >= 0x8000:
                print('  号 %d %s: 越出 charBase 块' % (tn, half))
                continue
            bits = tile_bits(vr, char_addr, tn)
            inks = sum(1 for row in bits for p in row if p >= 8)
            mark = ''
            if half == '上':
                mark = '  <<<'
            print('  号 %4d %s  墨点=%2d%s' % (tn, half, inks, mark))
            for row in bits:
                print('        ' + ''.join(
                    '#' if p >= 12 else ('+' if p >= 8 else ('.' if p == 0 else 'o'))
                    for p in row))
        if len(printed) > 60:
            print('  ...（省略）')
            break


if __name__ == '__main__':
    main()
