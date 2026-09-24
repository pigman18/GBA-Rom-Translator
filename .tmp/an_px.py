# -*- coding: utf-8 -*-
"""L2 判据（像素级）：从设置页 dump 里回答「红坨」是什么。

对每个被 BG0 map 引用的 tile 号，打印：
  pal  = tilemap 项的高 4 位（调色板 bank）
  vals = 该 tile 32 字节里 nibble 值的分布（只列出现过的值）
  -> 若 vals 里没有 0，说明「空白像素」被写成了非 0 色 ⇒ 整格满色 = 坨

同时打印窗口结构体（0x0202E658）的 0x00..0x30 字节，
重点是 WIN_COLOR_C/D/E(0x0C/0x0D/0x0E) 与 WIN_PALETTE(0x0F)。

用法: python .tmp/an_px.py <tag> [win_hex]
"""
import struct
import sys
import collections
import os

VRAM = 0x06000000
EWRAM = 0x02000000
SCR_ADDR = 0x06007800
CHAR_ADDR = 0x06008000


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else 'h1'
    win_addr = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x0202E658

    vr = open('.tmp/drive_%s_vram.bin' % tag, 'rb').read()
    ew = open('.tmp/drive_%s_ewram.bin' % tag, 'rb').read()

    # ---------------- 1) 窗口结构体 ----------------
    wo = win_addr - EWRAM
    print('=== 窗口 0x%08X ===' % win_addr)
    for off in range(0, 0x30, 0x10):
        bs = ew[wo + off: wo + off + 0x10]
        print('  +0x%02X: %s' % (off, ' '.join('%02X' % b for b in bs)))
    names = {0x00: 'TPL', 0x08: 'FONT_INDEX', 0x09: 'DELAY',
             0x0A: 'TEXTMODE', 0x0B: 'FONTNUM', 0x0C: 'COLOR_C(fg)',
             0x0D: 'COLOR_D(bg)', 0x0E: 'COLOR_E(sha)',
             0x0F: 'PALETTE', 0x16: 'TILE_BASE', 0x18: 'TILE_OFFSET',
             0x1A: 'CUR_X', 0x1B: 'CUR_TILE_X', 0x1C: 'CUR_Y',
             0x1D: 'CUR_TILE_Y'}
    for off, nm in sorted(names.items()):
        if off in (0x00, 0x16, 0x18):
            print('  %-16s +0x%02X = 0x%04X' % (nm, off,
                  struct.unpack_from('<H', ew, wo + off)[0]))
        else:
            print('  %-16s +0x%02X = %d' % (nm, off, ew[wo + off]))

    # ---------------- 2) map ----------------
    grid = [[struct.unpack_from('<H', vr, (SCR_ADDR - VRAM) + (r * 32 + c) * 2)[0]
             for c in range(32)] for r in range(32)]

    nums = collections.OrderedDict()
    for r in range(32):
        for c in range(32):
            v = grid[r][c]
            if v & 0x3FF:
                nums.setdefault(v & 0x3FF, []).append(((v >> 12) & 0xF, r, c))

    print()
    print('=== 每个 tile 号的像素值分布（pal=调色板 bank；vals=值:个数）===')
    solid = []
    for n in sorted(nums):
        o = (CHAR_ADDR - VRAM) + n * 32
        if o + 32 > len(vr):
            print('  号 %4d 越界' % n)
            continue
        cnt = collections.Counter(vr[o:o + 32])
        cnt.pop(0, None)
        pals = sorted(set(p for p, _, _ in nums[n]))
        zero = 32 - sum(cnt.values())
        tot = 32
        nz = sum(cnt.values()) * 2
        line = ('  号 %4d pal=%s  零半字节=%2d/64  非零值: %s'
                % (n, ','.join(str(p) for p in pals), zero,
                   ' '.join('%X:%d' % (k, v) for k, v in sorted(cnt.items()))))
        if zero == 0:
            line += '   <<<< 满格（无 0 像素）'
            solid.append(n)
        print(line)

    print()
    print('=== 满格号（无 0 像素）===')
    print('  %s' % solid)
    print('  共 %d 个' % len(solid))


if __name__ == '__main__':
    main()
