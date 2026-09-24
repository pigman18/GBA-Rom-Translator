#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
r4grid.py —— 从真机 dump 里读某一 BG 层的 tilemap 网格（原盘调研用，零旧代码依赖）

用法: python r4grid.py <tag> <bg>
数据: .tmp/drive_<tag>_vram.bin + .tmp/drive_<tag>.log 的 [io] 行
输出: 该层的 32x32 瓦片号网格 + 文字格统计
"""
import sys, re, os

D = r'C:\code\GBA-Rom-Translator\.tmp'
TAG = sys.argv[1]
BG = int(sys.argv[2])

vram = open(os.path.join(D, 'drive_%s_vram.bin' % TAG), 'rb').read()
log = open(os.path.join(D, 'drive_%s.log' % TAG), 'r',
           encoding='utf-8', errors='replace').read()


def ioread(name):
    m = re.search(r'\[io\] IO %s 0x[0-9a-f]+:\s*(0x[0-9a-fA-F]+)' % name, log)
    return int(m.group(1), 16) if m else None


disp = ioread('DISPCNT')
cnt = ioread('BG%dCNT' % BG)
if cnt is None:
    print('!! 该 dump 没有 BG%dCNT' % BG)
    sys.exit(1)

prio = cnt & 3
cb = (cnt >> 2) & 3
sb = (cnt >> 8) & 0x1f
bpp8 = (cnt >> 7) & 1
charbase = 0x4000 * cb
screenbase = 0x800 * sb
size = (disp >> 14) & 3 if BG < 2 else ((disp >> 14) & 3)

print('=== tag=%s  DISPCNT=%#06x ===' % (TAG, disp))
print('BG%dCNT=%#06x  prio=%d charBlock=%d(VRAM %#07x) screenBlock=%d(VRAM %#07x) %s'
      % (BG, cnt, prio, cb, 0x6000000 + charbase, sb, 0x6000000 + screenbase,
         '8bpp' if bpp8 else '4bpp'))
print('瓦片号 -> VRAM: tile n = %#07x + 32*n' % (0x6000000 + charbase))

MW = 32
mb = vram[screenbase:screenbase + MW * MW * 2]
grid = []
for r in range(MW):
    row = []
    for c in range(MW):
        e = mb[(r * MW + c) * 2] | (mb[(r * MW + c) * 2 + 1] << 8)
        row.append(e)
    grid.append(row)

# 屏幕可见区 30x20
VIS_R, VIS_C = 20, 30
print()
print('--- tile 号网格（低 10 位），%dx%d 可见区 ---' % (VIS_R, VIS_C))
hdr = '     ' + ''.join('%4d' % c for c in range(VIS_C))
print(hdr)
for r in range(VIS_R):
    line = ''.join('%4d' % (grid[r][c] & 0x3ff) for c in range(VIS_C))
    print('r%02d %s' % (r, line))

print()
print('--- 统计 ---')
seen = {}
for r in range(VIS_R):
    for c in range(VIS_C):
        e = grid[r][c] & 0x3ff
        seen.setdefault(e, []).append((r, c))
used = sorted(k for k in seen if k != 0)
print('非零格位 %d 个，不同瓦片号 %d 个' % (sum(len(v) for k, v in seen.items() if k),
                                     len(used)))
print('瓦片号范围 %d .. %d' % (used[0], used[-1]) if used else 'n/a')
odd = [k for k in used if k % 2 == 1]
print('奇数号 %d 个 / 偶数号 %d 个' % (len(odd), len(used) - len(odd)))

print()
print('--- 竖对检验：格 (r,c)=t 且 (r+1,c)=t+1 的"字形对" ---')
pairs = 0
pair_tiles = set()
for r in range(VIS_R - 1):
    for c in range(VIS_C):
        t = grid[r][c] & 0x3ff
        b = grid[r + 1][c] & 0x3ff
        if t and b == t + 1:
            pairs += 1
            pair_tiles.add(t)
print('竖对数 = %d，涉及上位瓦片 %d 个' % (pairs, len(pair_tiles)))

print()
print('--- 横对检验：格 (r,c)=t 且 (r,c+1)=t+1 ---')
hp = 0
for r in range(VIS_R):
    for c in range(VIS_C - 1):
        t = grid[r][c] & 0x3ff
        n = grid[r][c + 1] & 0x3ff
        if t and n == t + 1:
            hp += 1
print('横对数 = %d' % hp)

print()
print('--- 每行文字格位的瓦片号序列（跳 0）---')
for r in range(VIS_R):
    seq = [(c, grid[r][c] & 0x3ff) for c in range(VIS_C) if grid[r][c] & 0x3ff]
    if not seq:
        continue
    print('r%02d: %s' % (r, ' '.join('%d:%d' % (c, t) for c, t in seq)))
