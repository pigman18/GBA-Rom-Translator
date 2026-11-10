"""最终验证：小字与大字的码位一致性 + 并排对比。

═══ 267 已成功导出 2452 个小字 ═══
码 0x000 是「中」：竖线贯穿、方框在上，占 y=1..12（高 12）。

本脚本：
 ① 同一码位下，大字和小字并排渲染，确认是同一个字
 ② 统计两套字库的覆盖差异
 ③ 生成对比图
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
BASE = 0x08000000

IW205 = (ROOT / "work/_probe/runtime205/t000_prove_iwram.bin").read_bytes()
IW261 = (ROOT / "work/_probe/party261/s01_party01_iwram.bin").read_bytes()
PAL205 = IW205[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]
PAL261 = IW261[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]
IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]

PAGES_MAIN = [0x089C4230, 0x089555A0, 0x08B55564, 0x08A2725C, 0x08B333A0,
              0x08907C0C, 0x08AD690C, 0x08935A08, 0x08A72610, 0x08AB5404,
              0x089B2B0C]
PAGES_SMALL = [0x08B01000, 0x08B40000, 0x08B50000, 0x08B60000, 0x08B70000,
               0x08B80000, 0x08B90000, 0x08BA0000, 0x08BB0000,
               0x08B64000, 0x08B68000]
OUT = ROOT / "work" / "_probe" / "compare2"
OUT.mkdir(parents=True, exist_ok=True)


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


def decode16(src, pal):
    out = bytearray()
    for r3 in range(16):
        p = (r3 // 2) * 2
        v = src[p] if (r3 & 1) else (src[p + 1] if p + 1 < len(src) else 0)
        i = IDX[v]
        off = i * 2
        out += pal[off:off + 2] if off + 1 < len(pal) else b'\x00\x00'
    return bytes(out)


def mat8(blob):
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


def big_glyph(code):
    """大字：4 段（+0x00/+0x10/+0x100/+0x110），2x2 拼 16x16。"""
    hi, lo = code >> 8, code & 0xFF
    if hi >= len(PAGES_MAIN):
        return None
    a = PAGES_MAIN[hi] + lo * 64
    o = a - BASE
    if o < 0 or o + 0x120 > len(zh):
        return None
    segs = []
    for off in (0x00, 0x10, 0x100, 0x110):
        segs.append(mat8(decode16(zh[o + off:o + off + 16], PAL205)))
    return np.vstack([np.hstack([segs[0], segs[1]]),
                      np.hstack([segs[2], segs[3]])])


def small_glyph(code):
    """小字：2 段（+0x00/+0x100），纵向拼 8x16。"""
    hi, lo = code >> 8, code & 0xFF
    if hi >= len(PAGES_SMALL):
        return None
    a = PAGES_SMALL[hi] + lo * 64
    o = a - BASE
    if o < 0 or o + 0x110 > len(zh):
        return None
    d0 = mat8(decode16(zh[o:o + 16], PAL261))
    d1 = mat8(decode16(zh[o + 0x100:o + 0x100 + 16], PAL261))
    return np.vstack([d0, d1])


def ink(m, bg):
    return int((m != bg).sum())


def bg_of(m):
    from collections import Counter
    return Counter(int(v) for v in m.flatten()).most_common(1)[0][0]


# ── 统计 ─────────────────────────────────────────────────
print("=== 两套字库的覆盖 ===")
big_ok, small_ok = set(), set()
for code in range(0x0B00):
    b = big_glyph(code)
    if b is not None:
        bg = bg_of(b)
        if ink(b, bg) >= 6:
            big_ok.add(code)
    s = small_glyph(code)
    if s is not None:
        bg = bg_of(s)
        if ink(s, bg) >= 6:
            small_ok.add(code)
print(f"  大字有内容: {len(big_ok)}")
print(f"  小字有内容: {len(small_ok)}")
print(f"  两者都有  : {len(big_ok & small_ok)}")
print(f"  只在大字  : {len(big_ok - small_ok)}")
print(f"  只在小字  : {len(small_ok - big_ok)}")

# ── 并排对比图 ───────────────────────────────────────────
print("\n=== 生成并排对比图（左=大字16x16，右=小字8x16）===")
codes = sorted(big_ok & small_ok)[:64]
SCALE = 3
cols = 8
CW = (16 + 8 + 4) * SCALE + 6
CH = 16 * SCALE + 6
rows = (len(codes) + cols - 1) // cols
img = np.full((rows * CH, cols * CW, 3), 14, dtype=np.uint8)

for i, code in enumerate(codes):
    ry, rx = divmod(i, cols)
    y0 = ry * CH + 2
    x0 = rx * CW + 2
    b = big_glyph(code)
    s = small_glyph(code)
    bgb = bg_of(b)
    bgs = bg_of(s)
    # 大字
    for y in range(16):
        for x in range(16):
            v = int(b[y, x])
            g = 14 if v == bgb else (255 if v > bgb else 140)
            img[y0 + y * SCALE:y0 + (y + 1) * SCALE,
                x0 + x * SCALE:x0 + (x + 1) * SCALE] = (g, g, g)
    # 小字（放在大字右侧）
    xoff = 18 * SCALE
    for y in range(16):
        for x in range(8):
            v = int(s[y, x])
            g = 14 if v == bgs else (255 if v > bgs else 140)
            img[y0 + y * SCALE:y0 + (y + 1) * SCALE,
                x0 + xoff + x * SCALE:x0 + xoff + (x + 1) * SCALE] = (g, g, g)

p = OUT / "COMPARE.png"
save_png(p, img)
print(f"  ✔ {p}  ({img.shape[1]}x{img.shape[0]}, {len(codes)} 组)")

# ── 字符画：前 4 个码位并排 ──────────────────────────────
print("\n=== 前 4 个码位：大字(左) vs 小字(右) ===")
for code in sorted(big_ok & small_ok)[:4]:
    b = big_glyph(code)
    s = small_glyph(code)
    bgb, bgs = bg_of(b), bg_of(s)
    print(f"\n  码 0x{code:03X}")
    for y in range(16):
        lb = "".join("." if v == bgb else ("#" if v > bgb else "+") for v in b[y])
        ls = "".join("." if v == bgs else ("#" if v > bgs else "+") for v in s[y])
        print(f"    {lb}   {ls}")
