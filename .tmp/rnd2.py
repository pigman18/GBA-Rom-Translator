# -*- coding: utf-8 -*-
"""rnd2.py <tag> <bg> — 按 BGxHOFS/VOFS 对齐渲染（屏幕坐标 <- map 坐标）。"""
import struct, sys
from pathlib import Path
from PIL import Image
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")

def rgb555(w): return ((w&31)*255//31, ((w>>5)&31)*255//31, ((w>>10)&31)*255//31)

def main(tag, bi):
    bi = int(bi)
    v = (T / f"drive_{tag}_vram.bin").read_bytes()
    pal = (T / f"drive_{tag}_pal.bin").read_bytes()
    io = (T / f"drive_{tag}_io.bin").read_bytes()
    cnt = struct.unpack_from("<H", io, 0x08 + 2*bi)[0]
    hofs = struct.unpack_from("<H", io, 0x10 + 4*bi)[0] & 0x1FF
    vofs = struct.unpack_from("<H", io, 0x10 + 4*bi + 2)[0] & 0x1FF
    cb, sb, size = (cnt >> 2) & 3, (cnt >> 8) & 0x1F, (cnt >> 14) & 3
    W, H = {0: (32, 32), 1: (64, 32), 2: (32, 64), 3: (64, 64)}[size]
    cbase = cb * 0x4000
    off = sb * 0x800
    print("%s BG%d cb=%d sb=%d sz=%d W=%d HOFS=%d VOFS=%d" % (tag, bi, cb, sb, size, W, hofs, vofs))
    im = Image.new("RGB", (240, 160), (0, 0, 0))
    px = im.load()
    for sy in range(160):
        my = (sy + vofs) % (H*8)
        for sx in range(240):
            mx = (sx + hofs) % (W*8)
            tx, ty = mx >> 3, my >> 3
            e = struct.unpack_from("<H", v, off + (ty * W + tx) * 2)[0]
            t = e & 0x3FF
            bank = (e >> 12) & 0xF
            x, y = mx & 7, my & 7
            a = cbase + t * 32 + y * 4 + (x >> 1)
            byte = v[a] if a < len(v) else 0
            idx = (byte >> 4) if (x & 1) == 0 else (byte & 0xF)
            px[sx, sy] = rgb555(struct.unpack_from("<H", pal, (bank*16+idx)*2)[0])
    out = T / f"r2_{tag}_bg{bi}.png"
    im.resize((720, 480), Image.NEAREST).save(out)
    print("saved", out)

main(sys.argv[1], sys.argv[2])
