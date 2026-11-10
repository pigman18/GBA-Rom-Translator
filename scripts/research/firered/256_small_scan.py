"""小字页表用「主字库解码方式」解，看能否还原出 8x8 小字。

═══ 255 的观察 ═══
小字页 0x08B01000 的内容：
    ff ff db ff db ff 55 d5 9a da db db db db 55 d5
与主字库页 0x089C4230 的结构相同（FF 背景 + 低值笔画）。

但我用小字配置的「段0=+0x00, 段1=+0x100」去解，得到的全是背景 0x11。
而用 16 字节源 -> decode16，得到 32 字节，应该是 8x8。

问题可能在：
 A. 段0 的 16 字节不是给 8x8 用的（可能是给 8x16 的两半）
 B. 解码后还要再做一步映射
 C. PAL 不对（0x11 是背景色，说明解码出的像素对是 PAL[0]）

本脚本：把 0x08B01000 起的前 1KB 按各种步长/偏移直接画出来，
肉眼确认哪种能出小字。
"""
from __future__ import annotations

import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
iw = (ROOT / "work/_probe/party232/s05_party_iwram.bin").read_bytes()
vr = (ROOT / "work/_probe/party232/s05_party_vram.bin").read_bytes()
BASE = 0x08000000
OUT = ROOT / "work" / "_probe" / "smallf_scan"
OUT.mkdir(parents=True, exist_ok=True)

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = iw[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

PAGE0 = 0x08B01000


def save_png(path, arr):
    h, w, _ = arr.shape
    raw = b''.join(b'\x00' + arr[y].tobytes() for y in range(h))

    def chunk(tag, data):
        c = tag + data
        return (struct.pack('>I', len(data)) + c
                + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF))

    path.write_bytes(b'\x89PNG\r\n\x1a\n'
                     + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(raw, 9))
                     + chunk(b'IEND', b''))


import struct


def decode16(src):
    out = bytearray()
    for r3 in range(16):
        p = (r3 // 2) * 2
        v = src[p] if (r3 & 1) else (src[p + 1] if p + 1 < len(src) else 0)
        i = IDX[v]
        off = i * 2
        out += PAL[off:off + 2] if off + 1 < len(PAL) else b'\x00\x00'
    return bytes(out)


def mat8(blob32):
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob32[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


def render(mats, name, scale=4, cols=16):
    rows = (len(mats) + cols - 1) // cols
    cw, chh = 8 * scale + 2, 8 * scale + 2
    img = np.full((rows * chh, cols * cw, 3), 18, dtype=np.uint8)
    for i, m in enumerate(mats):
        ry, rx = divmod(i, cols)
        y0 = ry * chh + 1
        x0 = rx * cw + 1
        lo, hi = int(m.min()), int(m.max())
        rng = max(1, hi - lo)
        for y in range(8):
            for x in range(8):
                g = int((int(m[y, x]) - lo) * 255 / rng)
                img[y0 + y * scale:y0 + (y + 1) * scale,
                    x0 + x * scale:x0 + (x + 1) * scale] = (g, g, g)
    save_png(OUT / name, img)
    print(f"  ✔ {name}  ({img.shape[1]}x{img.shape[0]}, {len(mats)} 块)")


o = PAGE0 - BASE

# 方案 A：每 16B 一段 -> decode16 -> 32B 一个 8x8
print("=== A: 16B 源 -> decode16 -> 8x8（步长 16）===")
mats = []
for k in range(64):
    src = zh[o + k * 16:o + k * 16 + 16]
    mats.append(mat8(decode16(src)))
render(mats, "A_16step_decode.png")

# 方案 B：每 32B 直接当 8x8 4bpp
print("\n=== B: 32B 直接 8x8 4bpp（步长 32）===")
mats = []
for k in range(64):
    src = zh[o + k * 32:o + k * 32 + 32]
    mats.append(mat8(src))
render(mats, "B_32raw.png")

# 方案 C：主字库方式 —— 64B/字，4 段（+0/+0x10/+0x100/+0x110）
print("\n=== C: 主字库 4 段方式（步长 64）===")
mats = []
for k in range(32):
    base = o + k * 64
    parts = []
    for off in (0x00, 0x10, 0x100, 0x110):
        seg = zh[base + off:base + off + 16]
        if len(seg) < 16:
            seg = seg + bytes(16 - len(seg))
        parts.append(mat8(decode16(seg)))
    # 2x2 拼接
    comb = np.vstack([np.hstack([parts[0], parts[1]]),
                      np.hstack([parts[2], parts[3]])])
    mats.append(comb)
# 单独渲染 16x16
rows = (len(mats) + 8 - 1) // 8
scale = 2
cw, chh = 16 * scale + 2, 16 * scale + 2
img = np.full((rows * chh, 8 * cw, 3), 18, dtype=np.uint8)
for i, m in enumerate(mats):
    ry, rx = divmod(i, 8)
    y0 = ry * chh + 1
    x0 = rx * cw + 1
    lo, hi = int(m.min()), int(m.max())
    rng = max(1, hi - lo)
    for y in range(16):
        for x in range(16):
            g = int((int(m[y, x]) - lo) * 255 / rng)
            img[y0 + y * scale:y0 + (y + 1) * scale,
                x0 + x * scale:x0 + (x + 1) * scale] = (g, g, g)
save_png(OUT / "C_mainmethod.png", img)
print(f"  ✔ C_mainmethod.png")

# 方案 D：只取 +0x00 的 16B 一段（小字只看一段）
print("\n=== D: 只 +0x00 段（步长 64，取 16B）===")
mats = []
for k in range(64):
    base = o + k * 64
    mats.append(mat8(decode16(zh[base:base + 16])))
render(mats, "D_seg0.png")

# 关键验证：VRAM 小字 tile 137 能否在这些方案里找到
print("\n=== 验证：VRAM tile 137 的 32B 是否在上面的产物里 ===")
tgt = vr[137 * 32:137 * 32 + 32]
for k in range(256):
    src = zh[o + k * 16:o + k * 16 + 16]
    if len(src) < 16:
        break
    if decode16(src) == tgt:
        print(f"  步长16 命中 @ 块{k}")
        break
else:
    print("  步长16: 无")
for k in range(256):
    src = zh[o + k * 32:o + k * 32 + 32]
    if src == tgt:
        print(f"  步长32 原始命中 @ 块{k}")
        break
else:
    print("  步长32 原始: 无")
