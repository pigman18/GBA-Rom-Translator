"""调研(291) 解剖 EWRAM 小字缓冲 0x02000AC8 起，找出真实步长与来源。

═══ 290 的突破 ═══
VRAM 里 207 个真实小字 tile，25/30 能在 EWRAM 找到**逐字节完全相同**的副本：
    tile 3  -> EWRAM 0x02000AC8
    tile 6  -> EWRAM 0x02000B28  (+0x60)
    tile 9  -> EWRAM 0x02000B88  (+0x60)
    tile 10 -> EWRAM 0x02000BA8  (+0x20)
    tile 12 -> EWRAM 0x02000BE8

⇒ 小字缓冲在 EWRAM 0x02000AC8 一带，按 32 字节/tile 排。

本脚本：
 ① dump 0x02000A00..0x02002000，看结构
 ② 找「每字多少字节」的规律
 ③ 在 ROM 里搜这块缓冲的**没有的**部分（即从 ROM 复制来的源）
 ④ 若 EWRAM 里是解码结果，反推源
"""
from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
P = ROOT / "work" / "_probe" / "party261"
ew = (P / "s01_party01_ewram.bin").read_bytes()
vr = (P / "s01_party01_vram.bin").read_bytes()
iw = (P / "s01_party01_iwram.bin").read_bytes()
BASE = 0x08000000


def mat8(b):
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = b[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


START = 0x02000AC8
o = START - 0x02000000

print("=" * 78)
print(f"① EWRAM 0x{START:08X} 起 512 字节")
print("=" * 78)
for i in range(0, 512, 32):
    seg = ew[o + i:o + i + 32]
    m = mat8(seg)
    vals = set(int(v) for v in m.flatten())
    bg = max(vals, key=lambda v: int((m == v).sum())) if vals else 0
    ink = int((m != bg).sum())
    print(f"  0x{START + i:08X}  {seg.hex(' ')}  墨={ink}")

print("\n" + "=" * 78)
print("② 每 32 字节一块，看哪些是有效字形")
print("=" * 78)
valid = []
for i in range(0, 0x1000, 32):
    seg = ew[o + i:o + i + 32]
    if len(seg) < 32:
        break
    m = mat8(seg)
    vals = set(int(v) for v in m.flatten())
    if len(vals) > 4:
        continue
    bg = max(vals, key=lambda v: int((m == v).sum()))
    nz = (m != bg)
    ink = int(nz.sum())
    if 8 <= ink <= 50:
        valid.append((START + i, ink))
print(f"  有效块 {len(valid)} 个（在 0x1000 范围内）")
addrs = [a for a, _ in valid]
if len(addrs) > 1:
    ds = [addrs[i + 1] - addrs[i] for i in range(len(addrs) - 1)]
    print(f"  间隔分布: {dict(Counter(ds).most_common(8))}")

# ── 关键：这块缓冲是从哪来的 ────────────────────────────
print("\n" + "=" * 78)
print("③ 该缓冲的前 256 字节是否在 ROM 里")
print("=" * 78)
seg = ew[o:o + 256]
p = zh.find(seg)
print(f"  256B 整段: {'0x%08X' % (BASE + p) if p >= 0 else '-'}")
for ln in (128, 64, 32):
    cnt = 0
    for k in range(0, 256 - ln, 16):
        if zh.find(seg[k:k + ln]) >= 0:
            cnt += 1
    print(f"  {ln}B 子段命中 {cnt}")

# ── 该缓冲前后是什么 ────────────────────────────────────
print("\n" + "=" * 78)
print("④ 缓冲前后 256 字节（找表头/指针）")
print("=" * 78)
o2 = START - 0x200 - 0x02000000
for i in range(0, 0x300, 16):
    a = 0x02000000 + o2 + i
    seg = ew[o2 + i:o2 + i + 16]
    mark = ""
    if a <= START < a + 16:
        mark = "  <<< 缓冲起点"
    print(f"  0x{a:08X}  {seg.hex(' ')}{mark}")

# ── 用 ROM 里的页表 + decode16 解，看能否重现这块缓冲 ────
print("\n" + "=" * 78)
print("⑤ 尝试：该缓冲是否是某页表 decode16 的结果")
print("=" * 78)
IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = iw[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]


def decode16(src):
    out = bytearray()
    for r3 in range(16):
        p2 = (r3 // 2) * 2
        v = src[p2] if (r3 & 1) else (src[p2 + 1] if p2 + 1 < len(src) else 0)
        i = IDX[v]
        off = i * 2
        out += PAL[off:off + 2] if off + 1 < len(PAL) else b'\x00\x00'
    return bytes(out)


tgt = ew[o:o + 32]
for tbl, name in ((0x08B74000, "小字页表"), (0x089D08A0, "大字页表")):
    hits = 0
    for k in range(11):
        pv = struct.unpack_from('<I', zh, tbl - BASE + k * 4)[0]
        if not (BASE <= pv < BASE + len(zh)):
            continue
        for lo in range(0, 64):
            for stride_name, off in (("64", lo * 64), ("512", (lo >> 3) * 512 + (lo & 7) * 32)):
                a = pv + off
                oo = a - BASE
                if oo < 0 or oo + 16 > len(zh):
                    continue
                if decode16(zh[oo:oo + 16]) == tgt:
                    hits += 1
    print(f"  {name}: 命中 {hits}")
