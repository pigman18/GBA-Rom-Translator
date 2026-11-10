"""调研(292) 确认小字真实尺寸：EWRAM 是 8 位像素缓冲。

═══ 291 的关键 ═══
EWRAM 0x02000AC8 的数据：33 33 33 44 33 33 44 44 33 43 44 44...
值只有 0x33/0x44/0x55/0x11/0xff —— **每像素 1 字节**（8bpp），不是 4bpp nibble。

而 VRAM 里同样的 tile 是 4bpp（32 字节 = 8x8）。
⇒ EWRAM 是 **8bpp 展开态**，VRAM 是 **4bpp 压缩态**。
   32 字节 4bpp = 64 像素；对应 8bpp 就是 64 字节。

数据块 0x02000AC8 起，tile 3/6/9 间隔 0x60 = 96 字节。
96 字节 / 8bpp = 96 像素... 但 8x8 = 64，8x12 = 96！

⇒ **8 宽 x 12 高，8bpp = 96 字节/字**。与小字配置表「宽8 高0xC」完全吻合！

本脚本：
 ① 按 96 字节/字、8x12 8bpp 渲染 EWRAM 缓冲
 ② 确认字形成立
 ③ 追这块缓冲的写入者（ROM 里的代码）
 ④ 反推 ROM 源
"""
from __future__ import annotations

import struct
import zlib
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
P = ROOT / "work" / "_probe" / "party261"
ew = (P / "s01_party01_ewram.bin").read_bytes()
vr = (P / "s01_party01_vram.bin").read_bytes()
iw = (P / "s01_party01_iwram.bin").read_bytes()
BASE = 0x08000000
N = len(zh)
OUT = ROOT / "work" / "_probe" / "small8bpp"
OUT.mkdir(parents=True, exist_ok=True)

START = 0x02000AC8
o = START - 0x02000000


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


print("=" * 78)
print("① 按 8 宽 x 12 高 8bpp（96 字节/字）解析")
print("=" * 78)
GLYPH = 96
W, H = 8, 12
for gi in range(6):
    base = o + gi * GLYPH
    if base + GLYPH > len(ew):
        break
    buf = ew[base:base + GLYPH]
    vals = Counter(int(v) for v in buf)
    bg = vals.most_common(1)[0][0]
    print(f"\n  字{gi} @0x{START + gi * GLYPH:08X}  值分布={dict(vals.most_common(4))}")
    for y in range(H):
        row = buf[y * W:(y + 1) * W]
        print("    " + "".join("." if v == bg else "#" for v in row))

print("\n" + "=" * 78)
print("② 若按 8x12 成立，统计整个缓冲有多少字")
print("=" * 78)
n_valid = 0
for gi in range(0, 200):
    base = o + gi * GLYPH
    if base + GLYPH > len(ew):
        break
    buf = ew[base:base + GLYPH]
    vals = Counter(int(v) for v in buf)
    bg = vals.most_common(1)[0][0]
    ink = sum(1 for v in buf if v != bg)
    if 8 <= ink <= 80:
        n_valid += 1
print(f"  有效字 {n_valid} 个（在 200 个位置内）")

# ── 关键：这块缓冲由谁写 ─────────────────────────────────
print("\n" + "=" * 78)
print(f"③ 谁引用 0x{START:08X}")
print("=" * 78)
nd = struct.pack('<I', START)
pos = zh.find(nd)
hits = []
while pos >= 0:
    hits.append(BASE + pos)
    pos = zh.find(nd, pos + 1)
print(f"  精确引用 {len(hits)} 处: {[hex(h) for h in hits[:10]]}")

# 也搜邻近地址（缓冲可能有多个基址）
for delta in (-0x20, -0x40, 0, 0x20, 0x40, -0x80, 0x80):
    a = START + delta
    nd2 = struct.pack('<I', a)
    pos = zh.find(nd2)
    cnt = 0
    first = []
    while pos >= 0:
        cnt += 1
        if len(first) < 3:
            first.append(BASE + pos)
        pos = zh.find(nd2, pos + 1)
    if cnt:
        print(f"  0x{a:08X}: {cnt} 处 {[hex(x) for x in first]}")

# ── 该缓冲是否来自 ROM 的某页表 ──────────────────────────
print("\n" + "=" * 78)
print("④ 该缓冲的 8bpp 数据能否在 ROM 里找到（直接按字节）")
print("=" * 78)
seg = ew[o:o + 64]
p = zh.find(seg)
print(f"  前 64B: {'0x%08X' % (BASE + p) if p >= 0 else '-'}")
p = ja.find(seg)
print(f"  原版: {'0x%08X' % (BASE + p) if p >= 0 else '-'}")

# 取单字，搜 ROM
for gi in range(3):
    base = o + gi * GLYPH
    buf = ew[base:base + GLYPH]
    vals = Counter(int(v) for v in buf)
    bg = vals.most_common(1)[0][0]
    # 归一化成 0/1 掩码（12 行 x 1 字节 = 12 字节）
    mask = bytes(sum((1 << (7 - x)) for x in range(W)
                     if buf[y * W + x] != bg) for y in range(H))
    pz = zh.find(mask)
    pj = ja.find(mask)
    print(f"  字{gi} 掩码 {mask.hex()}: "
          f"汉化={'0x%08X' % (BASE + pz) if pz >= 0 else '-'}  "
          f"原版={'0x%08X' % (BASE + pj) if pj >= 0 else '-'}")
