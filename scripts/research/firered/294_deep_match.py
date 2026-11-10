"""调研(294) 深挖最后一步：为什么 2431 字和 VRAM 真实小字 0 命中。

═══ 现状 ═══
· 小字页表 0x08B74000，公式 addr = PAGES[hi] + (lo>>3)*512 + (code&7)*32
  解出 2431 字，肉眼可读（中 文 宝 可 梦 盘…），但 bbox 是 12x12
· VRAM 里有 207 个「真实小字 tile」（7-8 高、5-8 宽）
· 逐字节比对：0 命中

⇒ 两边形状不同（12x12 vs 8x8 级），说明**不是同一套**。

【本脚本穷举所有可能的「VRAM tile 来源」】
 ① 小字页表 4 段全拼 16x16 —— 裁成 8x8 各象限去比
 ② 4 段里任意 1 段 / 2 段组合
 ③ 4 段各自单独比（不拼）
 ④ 大字节表同样处理
 ⑤ EWRAM 缓冲里的 8bpp 数据裁成 8x8 去比
 ⑥ 若全不中，说明小字是**运行时缩放**产生

目标：把 VRAM tile 3（第一个真实小字）作为样本，穷举找它的来源。
"""
from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
P = ROOT / "work" / "_probe" / "party261"
vr = (P / "s01_party01_vram.bin").read_bytes()
ew = (P / "s01_party01_ewram.bin").read_bytes()
iw = (P / "s01_party01_iwram.bin").read_bytes()
BASE = 0x08000000
N = len(zh)

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = iw[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

SMALL = [0x08B01000, 0x08B40000, 0x08B50000, 0x08B60000, 0x08B70000,
         0x08B80000, 0x08B90000, 0x08BA0000, 0x08BB0000,
         0x08B64000, 0x08B68000]
MAIN = [0x089C4230, 0x089555A0, 0x08B55564, 0x08A2725C, 0x08B333A0,
        0x08907C0C, 0x08AD690C, 0x08935A08, 0x08A72610, 0x08AB5404,
        0x089B2B0C]


def mat8(b):
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = b[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


def decode16(src):
    out = bytearray()
    for r3 in range(16):
        p = (r3 // 2) * 2
        v = src[p] if (r3 & 1) else (src[p + 1] if p + 1 < len(src) else 0)
        i = IDX[v]
        off = i * 2
        out += PAL[off:off + 2] if off + 1 < len(PAL) else b'\x00\x00'
    return bytes(out)


# ── 目标：VRAM 里第一个真实小字 tile ─────────────────────
def is_small(m):
    vals = set(int(v) for v in m.flatten())
    if len(vals) > 4:
        return False
    bg = max(vals, key=lambda v: int((m == v).sum()))
    nz = (m != bg)
    ink = int(nz.sum())
    if ink < 8 or ink > 50:
        return False
    ys = np.flatnonzero(nz.any(axis=1))
    xs = np.flatnonzero(nz.any(axis=0))
    return 5 <= len(ys) <= 8 and 3 <= len(xs) <= 8


targets = {}
for t in range(len(vr) // 32):
    b = vr[t * 32:t * 32 + 32]
    if is_small(mat8(b)):
        targets[t] = b
print(f"VRAM 真实小字 tile: {len(targets)} 个")
T0 = sorted(targets)[0]
print(f"样本 tile {T0}: {targets[T0].hex(' ')}")
m0 = mat8(targets[T0])
for y in range(8):
    print("  " + "".join("#" if m0[y, x] not in (5, 0) else "." for x in range(8)))

tgt = targets[T0]

# ── 穷举：页表 × 公式 × 段组合 ──────────────────────────
print("\n" + "=" * 78)
print("穷举所有 (页表, 公式, 段偏移) 组合，找哪段解码 == 样本 tile")
print("=" * 78)

FORMULAS = {
    "lo64": lambda hi, lo, c: lo * 64,
    "512": lambda hi, lo, c: (lo >> 3) * 512 + (c & 7) * 32,
    "lo32": lambda hi, lo, c: lo * 32,
    "lo16": lambda hi, lo, c: lo * 16,
}
SEGS = [0x00, 0x10, 0x20, 0x30, 0x40, 0x60, 0x80, 0xC0, 0x100, 0x110,
        0x120, 0x140, 0x160, 0x200]

hits = []
for tbl_name, pages in (("SMALL", SMALL), ("MAIN", MAIN)):
    for fname, fn in FORMULAS.items():
        for seg in SEGS:
            n = 0
            for code in range(0x0B00):
                hi, lo = code >> 8, code & 0xFF
                if hi >= len(pages):
                    continue
                a = pages[hi] + fn(hi, lo, code) + seg
                o = a - BASE
                if o < 0 or o + 16 > N:
                    continue
                if decode16(zh[o:o + 16]) == tgt:
                    n += 1
            if n:
                hits.append((n, tbl_name, fname, seg))
hits.sort(reverse=True)
if hits:
    print("  命中：")
    for n, tn, fn, sg in hits[:10]:
        print(f"    {tn}/{fn}/+0x{sg:03X}: {n} 个码位")
else:
    print("  ✘ 全部 0 命中")

# ── 穷举：把 4 段拼出的 16x16 裁成 8x8 各象限 ────────────
print("\n" + "=" * 78)
print("穷举：16x16 拼图裁成 8x8 的 4 个象限")
print("=" * 78)
quad_hits = []
for tbl_name, pages in (("SMALL", SMALL), ("MAIN", MAIN)):
    for fname in ("lo64", "512"):
        fn = FORMULAS[fname]
        for code in range(0, 0x0B00):
            hi, lo = code >> 8, code & 0xFF
            if hi >= len(pages):
                continue
            base = pages[hi] + fn(hi, lo, code)
            o = base - BASE
            if o < 0 or o + 0x120 > N:
                continue
            segs = [mat8(decode16(zh[o + k:o + k + 16]))
                    for k in (0x00, 0x10, 0x100, 0x110)]
            # 各种拼法
            combos = {
                "2x2": np.vstack([np.hstack([segs[0], segs[1]]),
                                  np.hstack([segs[2], segs[3]])]),
                "h0_10": np.hstack([segs[0], segs[1]]),
                "v0_10": np.vstack([segs[0], segs[1]]),
                "h0_100": np.hstack([segs[0], segs[2]]),
            }
            for cname, cv in combos.items():
                if cv.shape[0] >= 8 and cv.shape[1] >= 8:
                    for qy in range(0, cv.shape[0] - 7, 8):
                        for qx in range(0, cv.shape[1] - 7, 8):
                            quad = cv[qy:qy + 8, qx:qx + 8]
                            blob = bytearray(32)
                            for y in range(8):
                                for x in range(8):
                                    v = int(quad[y, x]) & 0xF
                                    if x % 2 == 0:
                                        blob[y * 4 + x // 2] |= v
                                    else:
                                        blob[y * 4 + x // 2] |= v << 4
                            if bytes(blob) == tgt:
                                quad_hits.append((tbl_name, fname, cname,
                                                  code, (qy, qx)))
if quad_hits:
    print(f"  命中 {len(quad_hits)}:")
    for x in quad_hits[:10]:
        print(f"    {x}")
else:
    print("  ✘ 0 命中")

# ── 最后：样本 tile 是否等于 EWRAM 某块 ──────────────────
print("\n" + "=" * 78)
print("EWRAM 里找样本 tile（8bpp -> 4bpp 转换后）")
print("=" * 78)
# EWRAM 是 8bpp，VRAM 是 4bpp。若 EWRAM 值 <= 15，可看成 nibble
for stride in (64, 96, 32):
    found = 0
    for k in range(0, len(ew) - stride, 16):
        buf = ew[k:k + stride]
        # 取前 32 字节，若都 <=15，压成 4bpp
        if any(v > 15 for v in buf[:32]):
            continue
        blob = bytearray(32)
        for y in range(8):
            for x in range(8):
                v = buf[y * stride // 8 + x] if stride >= 64 else buf[y * 4 + x // 2]
                v &= 0xF
                if x % 2 == 0:
                    blob[y * 4 + x // 2] |= v
                else:
                    blob[y * 4 + x // 2] |= v << 4
        if bytes(blob) == tgt:
            found += 1
    print(f"  stride {stride}: 命中 {found}")
