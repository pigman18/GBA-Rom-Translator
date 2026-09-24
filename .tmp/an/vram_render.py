# -*- coding: utf-8 -*-
"""vram_render.py - 从 dump 的 VRAM/PAL/IO 直接渲染 GBA 画面（BG 层），
  不依赖模拟器截图，精确还原 tilemap+charBase+palette。
用法： python vram_render.py <tag> [--bg 0] [--crop x0 y0 x1 y1]
"""
from __future__ import annotations
import sys
import os

import numpy as np

ROOT = r"C:\code\GBA-Rom-Translator"
TMP = os.path.join(ROOT, ".tmp")
VRAM_BASE = 0x06000000
RAMP = " .:-=+*#%@"

def load(tag, suffix):
    p = os.path.join(TMP, "drive_%s_%s.bin" % (tag, suffix))
    return open(p, "rb").read()

def read_io(tag):
    d = load(tag, "io")
    return {0x04000000 + i: d[i] | (d[i + 1] << 8) for i in range(0, len(d) - 1, 2)}

def parse_cnt(v):
    cb = (v >> 2) & 3
    sb = (v >> 8) & 0x1F
    return cb * 0x4000, sb * 0x800, bool(v & 0x8000)

def render_bg(vr, pal, cnt, size_reg=0):
    """size_reg: BGnSIZE (0x04000020+4*n). 返回 (H, W, 3) uint8。"""
    cb, sb, is_256 = parse_cnt(cnt)
    # 文本 size: 256x256 (reg=0) / 512x256 (1) / 256x512 (2) / 512x512 (3)
    w = 256 if (size_reg & 1) == 0 else 512
    h = 256 if (size_reg & 2) == 0 else 512
    w = min(w, 240); h = min(h, 160)  # 只画可视区
    if is_256:
        return None
    out = np.zeros((h, w, 3), np.uint8)
    pal_np = np.zeros((256, 3), np.int32)
    for i in range(256):
        v = pal[i * 2] | (pal[i * 2 + 1] << 8)
        pal_np[i] = ((v & 0x1F) * 255 // 31,
                     ((v >> 5) & 0x1F) * 255 // 31,
                     ((v >> 10) & 0x1F) * 255 // 31)
    for r in range(h):
        ty = r // 8
        py = r % 8
        for c in range(w):
            tx = c // 8
            px = c % 8
            moff = sb + (ty * 32 + tx) * 2
            if moff + 1 >= len(vr):
                continue
            t = vr[moff] | (vr[moff + 1] << 8)
            bank = (t >> 12) & 0xF
            tile = t & 0x3FF
            flip_x = bool(t & 0x400)
            flip_y = bool(t & 0x800)
            row = (7 - py) if flip_y else py
            col = (7 - px) if flip_x else px
            toff = cb + tile * 32 + row * 4 + col // 2
            if toff >= len(vr):
                continue
            b = vr[toff]
            idx = (b >> 4) if (col & 1) == 0 else (b & 0xF)
            out[r, c] = pal_np[(bank * 16 + idx) & 0xFF]
    return out

def to_ascii(img):
    lum = (img[..., 0].astype(np.float32) * 0.299
           + img[..., 1].astype(np.float32) * 0.587
           + img[..., 2].astype(np.float32) * 0.114) / 255.0
    idx = np.clip((lum * (len(RAMP) - 1) * 1.7).astype(np.int32), 0, len(RAMP) - 1)
    return "\n".join("".join(RAMP[v] for v in row) for row in idx)

def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "v10menu"
    bg = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    io = read_io(tag)
    vr = load(tag, "vram")
    pal = load(tag, "pal")
    cnt = io.get(0x04000008 + bg * 2, 0)
    size_reg = io.get(0x04000020 + bg * 4, 0)
    cb, sb, _ = parse_cnt(cnt)
    print("tag=%s BG%dCNT=0x%04X charBase=0x%08X screenBase=0x%08X"
          % (tag, bg, cnt, VRAM_BASE + cb, VRAM_BASE + sb))
    img = render_bg(vr, pal, cnt, size_reg)
    if img is None:
        print("256-color BG not supported")
        return
    print(to_ascii(img))

if __name__ == "__main__":
    main()
