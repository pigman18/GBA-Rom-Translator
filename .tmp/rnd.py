# -*- coding: utf-8 -*-
"""rnd.py <tag> <bg> — 用真调色板把某 BG 层渲染成 PNG（240x160 可见区）。"""
import struct, sys
from pathlib import Path
from PIL import Image
T = Path(r"C:/code/GBA-Rom-Translator/.tmp")

def rgb555(w):
    return ((w & 31) * 255 // 31, ((w >> 5) & 31) * 255 // 31, ((w >> 10) & 31) * 255 // 31)

def main(tag, bi):
    bi = int(bi)
    v = (T / f"drive_{tag}_vram.bin").read_bytes()
    pal = (T / f"drive_{tag}_pal.bin").read_bytes()
    io = struct.unpack_from("<HH", (T / f"drive_{tag}_io.bin").read_bytes(), 0)
    cnt = struct.unpack_from("<H", (T / f"drive_{tag}_io.bin").read_bytes(), 0x08 + 2*bi)[0]
    cb, sb, size = (cnt >> 2) & 3, (cnt >> 8) & 0x1F, (cnt >> 14) & 3
    W, H = {0: (32, 32), 1: (64, 32), 2: (32, 64), 3: (64, 64)}[size]
    cbase = cb * 0x4000
    off = sb * 0x800
    im = Image.new("RGB", (240, 160), (0, 0, 0))
    px = im.load()
    for ty in range(20):
        for tx in range(30):
            e = struct.unpack_from("<H", v, off + (ty * W + tx) * 2)[0]
            t = e & 0x3FF
            bank = (e >> 12) & 0xF
            for y in range(8):
                for x in range(8):
                    a = cbase + t * 32 + y * 4 + (x >> 1)
                    byte = v[a] if a < len(v) else 0
                    idx = (byte >> 4) if (x & 1) == 0 else (byte & 0xF)
                    px[tx*8+x, ty*8+y] = rgb555(struct.unpack_from("<H", pal, (bank*16+idx)*2)[0])
    out = T / f"rnd_{tag}_bg{bi}.png"
    im.resize((480, 320), Image.NEAREST).save(out)
    print("saved", out)

main(sys.argv[1], sys.argv[2])
