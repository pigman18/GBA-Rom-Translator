# -*- coding: utf-8 -*-
"""模拟 chs_cell_from_1bpp -> extract_cols -> blend_glyph_4bpp，与 dump 的砖比对。"""
import sys
from pathlib import Path
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")
rom = (Path(r"C:/code/GBA-Rom-Translator/roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba")).read_bytes()
v = (T/"drive_z1_opt_vram.bin").read_bytes()
BIG = 0x09500000 - 0x08000000
CB = 2*0x4000

def cell(slot, w=11, rows=11, line_off=2):
    """1bpp 位流 -> 128B cell（墨15/阴影14/底0），布局 [TL][BL][TR][BR]"""
    bits = rom[BIG+slot*16: BIG+(slot+1)*16]
    ink = [[0]*16 for _ in range(16)]
    for r in range(rows):
        for x in range(w):
            bi = r*w + x
            if (bits[bi>>3] >> (7-(bi&7))) & 1: ink[line_off+r][x] = 1
    out = bytearray(128)
    for r in range(16):
        for half in range(2):
            for x in range(8):
                gx = half*8 + x
                if ink[r][gx]: val = 15
                elif r>=1 and gx>=1 and ink[r-1][gx-1]: val = 14
                else: val = 0
                o = (0x40 if half else 0x00) if r < 8 else (0x60 if half else 0x20)
                out[o + (r&7)*4 + (x>>1)] |= val << (4 if (x&1) else 0)
    return bytes(out)

def extract_cols(g128, xs, w):
    tl, bl, tr, br = g128[0:32], g128[32:64], g128[64:96], g128[96:128]
    up = [[0]*8 for _ in range(8)]; lo = [[0]*8 for _ in range(8)]
    for j in range(min(w,8)):
        sc = xs + j
        if sc >= 16: continue
        su, sl, c = (tl, bl, sc) if sc < 8 else (tr, br, sc-8)
        for r in range(8):
            bu = su[r*4 + (c>>1)]; bb = sl[r*4 + (c>>1)]
            up[r][j] = (bu>>4) if (c&1) else (bu & 0xF)
            lo[r][j] = (bb>>4) if (c&1) else (bb & 0xF)
    return up, lo

def blend(dst, val8, width, start, colors):
    """dst: 8x8 值表(会被改)，val8: 8x8 字模值，width/start"""
    mask = (0,0xFFFFFFFF,0xFFFFFFF0,0xFFFFF000,0xFFFF0000,0xFFF00000,0xFF000000,0xF0000000,0)[width]
    keep = mask if start==0 else mask  # 简化：仅 start>=0
    for r in range(8):
        for p in range(width):
            if start+p >= 8: break
            dst[r][start+p] = colors[val8[r][p]]

def simulate(slots, pool0, colors):
    """返回 {tile: 8x8 值表}, 以及 map 格序列"""
    tiles = {}
    def ensure(t): 
        tiles.setdefault(t, [[0]*8 for _ in range(8)])
        return tiles[t]
    pool = pool0; phase = 0; last = 0; tx = 0; grid = []
    for s in slots:
        g = cell(s)
        w0 = min(8-phase, 11); w1 = 11 - w0
        if phase == 0:
            t0 = pool; pool += 2
        else:
            t0 = last
        t1 = None
        if w1:
            t1 = pool; pool += 2
        adv = max(1, (phase+12) >> 3)
        up, lo = extract_cols(g, 0, w0)
        blend(ensure(t0), up, w0, phase, colors)
        blend(ensure(t0+1), lo, w0, phase, colors)
        if w1:
            up2, lo2 = extract_cols(g, w0, w1)
            blend(ensure(t1), up2, w1, 0, colors)
            blend(ensure(t1+1), lo2, w1, 0, colors)
        grid.append((t0, t1))
        tx += adv
        phase = (phase + 12) & 7
        last = t1 if w1 else t0
    return tiles, grid

def dumpval(t):
    return [[ (lambda b: ((b>>4) if (x&1)==0 else (b&0xF)))(v[CB+t*32+y*4+(x>>1)]) for x in range(8)] for y in range(8)]

SLOTS = [633, 1085, 2684, 621]   # 对话速度
COLORS = [0]*16
COLORS[15] = 8   # 墨 -> 8 (fg_ov)
COLORS[14] = 8   # 阴影 -> 8 (COLOR_E)
COLORS[0]  = 15  # 底 -> 15 (COLOR_D)
tiles, grid = simulate(SLOTS, 527, COLORS)
print("模拟 map 格/tile 序列:", grid)
for t in (527, 529, 531, 533, 535, 537):
    exp = tiles.get(t, [[0]*8 for _ in range(8)])
    act = dumpval(t)
    diff = sum(1 for r in range(8) for c in range(8) if exp[r][c]!=act[r][c])
    print("tile %d 差异 %2d/64" % (t, diff))
    for lbl, m in (("EXP", exp), ("ACT", act)):
        for r in range(8):
            pass
    if t in (527, 533):
        print("  期望:")
        for r in range(8): print("    " + "".join("#" if exp[r][c] else "." for c in range(8)))
        print("  实际:")
        for r in range(8): print("    " + "".join("#" if act[r][c] else "." for c in range(8)))
