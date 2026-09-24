# -*- coding: utf-8 -*-
"""optrender.py — 用真调色板把设置页 BG0 整层渲染出来，做两组对照：
  A: 全部号都按 cbase + t*32 取（硬件真实行为）
  B: 把 t>=512 的格子填成洋红（看我方/引擎高号砖占了多少屏面）
并输出「t>=512 那批砖」的像素（配真调色板），判断是边框美术还是字模残片。
"""
import os
import re
import struct
from PIL import Image

T = r"C:\code\GBA-Rom-Translator\.tmp"
VRAM = 0x06000000


def load(tag):
    v = open(os.path.join(T, "drive_%s_vram.bin" % tag), "rb").read()
    txt = open(os.path.join(T, "drive_%s.log" % tag), encoding="utf-8", errors="replace").read()
    io = {}
    for m in re.finditer(r"\[io\] IO (\w+) 0x[0-9a-fA-F]+:\s*(0x[0-9a-fA-F]+)", txt):
        io[m.group(1)] = int(m.group(2), 16)
    return v, io


def rgb555(w):
    r = (w & 31) * 255 // 31
    g = ((w >> 5) & 31) * 255 // 31
    b = ((w >> 10) & 31) * 255 // 31
    return (r, g, b)


def get_bgpal(v):
    """BG palette 在 0x05000000，不在 VRAM dump 里。用 ROM 里默认调色板？这里先尝试从 dump 找不到就返回 None。"""
    return None


def render(v, cells, cbase, pal, mask_hi=False, W=240, H=160):
    im = Image.new("RGB", (W, H), (0, 0, 0))
    for (tx, ty), t in cells.items():
        px0, py0 = tx * 8, ty * 8
        if px0 >= W or py0 >= H:
            continue
        body = (255, 0, 255) if (mask_hi and t >= 512) else None
        off = cbase + t * 32
        for y in range(8):
            if py0 + y >= H:
                break
            for x in range(8):
                if px0 + x >= W:
                    break
                b = v[off + y * 4 + x // 2]
                c = (b & 0xF) if x % 2 == 0 else (b >> 4)
                im.putpixel((px0 + x, py0 + y), body if body else pal[c])
    return im


def tile_img(v, off, pal, scale=5):
    im = Image.new("RGB", (8 * scale, 8 * scale))
    for y in range(8):
        for x in range(8):
            b = v[off + y * 4 + x // 2]
            c = (b & 0xF) if x % 2 == 0 else (b >> 4)
            for dy in range(scale):
                for dx in range(scale):
                    im.putpixel((x * scale + dx, y * scale + dy), pal[c])
    return im


def strip(v, tiles, aoff, pal, cols=8, scale=5):
    rows = (len(tiles) + cols - 1) // cols
    im = Image.new("RGB", (cols * 8 * scale, rows * 8 * scale), (30, 30, 36))
    for i, t in enumerate(tiles):
        gx, gy = i % cols, i // cols
        im.paste(tile_img(v, aoff + t * 32, pal, scale), (gx * 8 * scale, gy * 8 * scale))
    return im


TAG = os.environ.get("TAG", "optIO")
v, io = load(TAG)
# 真 BG 调色板：drive_v_opt_pal.bin（1024B = BG 256 + OBJ 256 个 RGB555），取 BG 段
pal = [(128, 128, 128)] * 16
pp = os.path.join(T, "drive_v_opt_pal.bin")
if os.path.exists(pp):
    pb = open(pp, "rb").read()
    pal = [rgb555(struct.unpack_from("<H", pb, i * 2)[0]) for i in range(16) if i * 2 + 2 <= len(pb)]
    if not pal:
        pal = [(128, 128, 128)] * 16

cnt = io["BG0CNT"]
cb = (cnt >> 2) & 3
sb = (cnt >> 8) & 0x1F
size = (cnt >> 14) & 3
cbase = cb * 0x4000
mbase = sb * 0x800

cells = {}
for ty in range(32 << size):
    for tx in range(32):
        o = mbase + (ty * 32 + tx) * 2
        cells[(tx, ty)] = struct.unpack_from("<H", v, o)[0] & 0x3FF

render(v, cells, cbase, pal).resize((720, 480), Image.NEAREST).save(os.path.join(T, "r_%s_all.png" % TAG))
render(v, cells, cbase, pal, mask_hi=True).resize((720, 480), Image.NEAREST).save(os.path.join(T, "r_%s_mask.png" % TAG))

hit = sorted(set(t for t in cells.values() if t >= 512))
strip(v, hit, cbase, pal, cols=8).save(os.path.join(T, "r_%s_hit.png" % TAG))
# cb3 整块头部 0..63 砖
strip(v, list(range(64)), 3 * 0x4000, pal, cols=8).resize((8 * 8 * 3, 8 * 8 * 3 * 1), Image.NEAREST).save(os.path.join(T, "r_cb3head.png"))
print("hit tiles:", hit)
print("count refs>=512:", sum(1 for t in cells.values() if t >= 512))
print("cb3 phys nonzero tiles:")
nz = [t for t in range(512) if any(v[3 * 0x4000 + t * 32:3 * 0x4000 + t * 32 + 32])]
print("  ", nz[:60], "..." if len(nz) > 60 else "")
print("saved r_opt_all.png r_opt_mask.png r_opt_hit.png r_cb3head.png")
