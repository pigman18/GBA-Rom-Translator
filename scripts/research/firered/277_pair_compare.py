"""严格对比：同一码位的大字与小字，放大并排。

═══ 为什么要这样比 ═══
小字图看起来「笔画极粗、几乎填满格子」，与「小字」这个名称不符。
两种可能：
  A. 小字是独立设计的 8x8 字模（笔画本来就粗，是正常的点阵小字）
  B. 小字只是把大字压扁/裁切，那就不该叫「一套独立的字库」

本脚本把同一码位的大字（16x16）和小字（8x16）并排放，放大 10 倍，
逐字对照笔画差异。
"""
from __future__ import annotations

import struct
import zlib
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
IW205 = (ROOT / "work/_probe/runtime205/t000_prove_iwram.bin").read_bytes()
IW261 = (ROOT / "work/_probe/party261/s01_party01_iwram.bin").read_bytes()
BASE = 0x08000000
N = len(zh)
OUT = ROOT / "work" / "_probe" / "pair_compare"
OUT.mkdir(parents=True, exist_ok=True)

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL205 = IW205[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]
PAL261 = IW261[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

PAGES_MAIN = [0x089C4230, 0x089555A0, 0x08B55564, 0x08A2725C, 0x08B333A0,
              0x08907C0C, 0x08AD690C, 0x08935A08, 0x08A72610, 0x08AB5404,
              0x089B2B0C]
PAGES_SMALL = [0x08B01000, 0x08B40000, 0x08B50000, 0x08B60000, 0x08B70000,
               0x08B80000, 0x08B90000, 0x08BA0000, 0x08BB0000,
               0x08B64000, 0x08B68000]


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


def mat8(b):
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = b[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


def big(code):
    hi, lo = code >> 8, code & 0xFF
    if hi >= len(PAGES_MAIN):
        return None
    o = PAGES_MAIN[hi] + lo * 64 - BASE
    if o < 0 or o + 64 > N:
        return None
    s = [mat8(decode16(zh[o + k * 16:o + k * 16 + 16], PAL205)) for k in range(4)]
    return np.vstack([np.hstack([s[0], s[1]]), np.hstack([s[2], s[3]])])


def small(code):
    hi, lo = code >> 8, code & 0xFF
    if hi >= len(PAGES_SMALL):
        return None
    o = PAGES_SMALL[hi] + lo * 64 - BASE
    if o < 0 or o + 64 > N:
        return None
    o1 = o + 0x100
    if o1 + 16 > N:
        return None
    return np.vstack([mat8(decode16(zh[o:o + 16], PAL261)),
                      mat8(decode16(zh[o1:o1 + 16], PAL261))])


SCALE = 10
GAP = 8
PAIRS = 8          # 每张图 8 组
COLS = 4

codes = list(range(0, PAIRS))
rows = (len(codes) + COLS - 1) // COLS
CW = (16 + 4 + 8) * SCALE + GAP   # 大字16 + 间隔 + 小字8
CH = 16 * SCALE + GAP
img = np.full((rows * CH, COLS * CW, 3), 10, dtype=np.uint8)

print("=== 并排对比（左大字16x16 / 右小字8x16）===")
for i, code in enumerate(codes):
    b = big(code)
    s = small(code)
    if b is None or s is None:
        continue
    ry, rx = divmod(i, COLS)
    y0 = ry * CH + 4
    x0 = rx * CW + 4
    bgb = Counter(int(v) for v in b.flatten()).most_common(1)[0][0]
    bgs = Counter(int(v) for v in s.flatten()).most_common(1)[0][0]

    # 大字
    for y in range(16):
        for x in range(16):
            v = int(b[y, x])
            g = 10 if v == bgb else (255 if v > bgb else 120)
            img[y0 + y * SCALE:y0 + (y + 1) * SCALE,
                x0 + x * SCALE:x0 + (x + 1) * SCALE] = (g, g, g)
    # 小字
    xoff = (16 + 4) * SCALE
    for y in range(16):
        for x in range(8):
            v = int(s[y, x])
            g = 10 if v == bgs else (255 if v > bgs else 120)
            img[y0 + y * SCALE:y0 + (y + 1) * SCALE,
                x0 + xoff + x * SCALE:x0 + xoff + (x + 1) * SCALE] = (g, g, g)

    # 统计笔画宽度
    def stroke_width(m, bg):
        ws = []
        for y in range(m.shape[0]):
            run = 0
            for x in range(m.shape[1]):
                if m[y, x] != bg:
                    run += 1
                elif run:
                    ws.append(run)
                    run = 0
            if run:
                ws.append(run)
        return np.mean(ws) if ws else 0

    print(f"  码 0x{code:03X}: 大字笔画宽 {stroke_width(b, bgb):.1f}px  "
          f"小字笔画宽 {stroke_width(s, bgs):.1f}px  "
          f"大字墨 {int((b != bgb).sum())}/256  小字墨 {int((s != bgs).sum())}/128")

p = OUT / "PAIRS_8.png"
save_png(p, img)
print(f"\n  ✔ {p}  ({img.shape[1]}x{img.shape[0]})")
