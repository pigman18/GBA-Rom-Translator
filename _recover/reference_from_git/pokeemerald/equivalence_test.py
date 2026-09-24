#!/usr/bin/env python3
"""draw_tile（text_render.c）golden 回归基线（离线，纯 python）。

对现役实现的三段循环合成器做位真直译，穷举其真实参数域
（inplace12_core：pass1 恒 width=8；pass2 width ∈ [0,4]；
 startPixel ∈ [0,7]；spill 由 startPixel+width>8 触发且 spillTile 必供），
在固定随机底图/墨迹/调色下产出全表 SHA256。

用途：任何触碰 draw_tile / 其查找假设的改动，重跑本脚本必须得到同一指纹；
换实现（如未来接 ref_glyph_copy，见 copy_glyph_to_tiles.c 头注的
swap-packed 契约讨论）则需显式重新生成指纹并在 A/B 说明中记录差异。"""

import hashlib
import random

def get_px(tile, x, y):
    b = tile[y*4 + (x >> 1)]
    return (b & 0xF) if (x & 1) else (b >> 4)

def put_px(tile, x, y, ink):
    i = y*4 + (x >> 1)
    if x & 1: tile[i] = (tile[i] & 0xF0) | (ink & 0xF)
    else:     tile[i] = (tile[i] & 0x0F) | ((ink & 0xF) << 4)

def draw_tile_py(dest_in, spill_in, start_pixel, width, color_d, temp32):
    """text_render.c draw_tile 慢路径直译。temp32 = 展开后 32B（CopyGlyph2bppTo4bpp_Origin 产物）。"""
    need_spill = (spill_in is not None) and (start_pixel + width > 8)
    dest = bytearray(dest_in)
    sp = bytearray(spill_in) if need_spill else None
    for r in range(8):
        for c in range(start_pixel, min(start_pixel + width, 8)):
            put_px(dest, c, r, color_d)
        if need_spill:
            for c in range(0, min(start_pixel + width - 8, 8)):
                put_px(sp, c, r, color_d)
        for c in range(width):
            dc = start_pixel + c
            if dc < 8:
                put_px(dest, dc, r, get_px(temp32, c, r))
            elif need_spill:
                put_px(sp, dc - 8, r, get_px(temp32, c, r))
        if start_pixel + width < 8:
            for c in range(start_pixel + width, 8):
                put_px(dest, c, r, color_d)
        if need_spill and start_pixel + width > 8:
            for c in range(start_pixel + width - 8, 8):
                put_px(sp, c, r, color_d)
    return bytes(dest), bytes(sp) if need_spill else None

def fingerprint():
    rnd = random.Random(20260827)
    digest = hashlib.sha256()
    cases = []
    for sp in range(8):
        cases.append((sp, 8, True))            # pass1 形态
        for w2 in range(0, 5):                 # pass2 形态（width 0..4）
            cases.append((sp, w2, True))
            cases.append((sp, w2, False))
    for _ in range(20000):                     # 随机覆盖层（合法域内）
        sp = rnd.randrange(8)
        w = rnd.choice([8, 8, rnd.randrange(1, 5)])
        have_spill = rnd.random() < .5
        cases.append((sp, w, have_spill))

    for sp, w, have_spill in cases:
        gw = sp + w
        spill_exists = have_spill and gw > 8
        base_dest = bytes(rnd.getrandbits(8) for _ in range(32))
        base_spill = bytes(rnd.getrandbits(8) for _ in range(32)) if spill_exists else None
        temp32 = bytes(rnd.getrandbits(8) for _ in range(32))
        cd = rnd.randrange(16)
        d, s = draw_tile_py(base_dest, base_spill, sp, w, cd, temp32)
        digest.update(bytes([sp, w, int(bool(spill_exists)), cd]))
        digest.update(d)
        if s is not None:
            digest.update(s)
    return digest.hexdigest()

if __name__ == "__main__":
    fp = fingerprint()
    print("draw_tile baseline fingerprint:", fp)
