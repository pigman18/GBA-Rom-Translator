"""核实：主字库每字 64B，究竟有几段有内容？字形真实尺寸是多少？

═══ 236 的惊人发现 ═══
对全部 2816 个码位的**第 0 段**解码，字形高度全部是 0（全空）。
但我 207 号脚本导出的字库明明是清晰的 12×16 汉字……

矛盾解析：207 用的是
    ms = [decode16(b[k*16:(k+1)*16]) for k in range(4)]
    np.vstack([np.hstack([ms0, ms1]), np.hstack([ms2, ms3])])
即 2x2 拼接。

若只有某些段有内容，2x2 拼出来仍能成字（只是位置错开）。
本脚本逐段统计，确认到底哪几段有墨、字形真实尺寸。
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
P = ROOT / "work" / "_probe" / "party232"
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
iw = (P / "s05_party_iwram.bin").read_bytes()
BASE = 0x08000000

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = iw[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]
PAGES4 = [0x089C4230, 0x089555A0, 0x08B55564, 0x08A2725C, 0x08B333A0,
          0x08907C0C, 0x08AD690C, 0x08935A08, 0x08A72610, 0x08AB5404,
          0x089B2B0C]


def decode16(src: bytes) -> bytes:
    out = bytearray()
    for r3 in range(16):
        p = (r3 // 2) * 2
        v = src[p] if (r3 & 1) else (src[p + 1] if p + 1 < len(src) else 0)
        i = IDX[v]
        off = i * 2
        out += PAL[off:off + 2] if off + 1 < len(PAL) else b'\x00\x00'
    return bytes(out)


def nibs(b):
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = b[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


def seg_stats(seg32: bytes):
    m = nibs(seg32)
    txt = (m == 11) | (m == 12)
    ys = np.flatnonzero(txt.any(axis=1))
    xs = np.flatnonzero(txt.any(axis=0))
    return len(ys), len(xs), int(txt.sum())


print("=== 逐段统计（每字 4 段）===")
for k in range(4):
    hc = Counter()
    inksum = 0
    nz = 0
    for pg in PAGES4:
        for lo in range(256):
            o = pg + lo * 64 - BASE
            if o < 0 or o + 64 > len(zh):
                continue
            d = decode16(zh[o + k * 16:o + k * 16 + 16])
            h, w, ink = seg_stats(d)
            hc[h] += 1
            inksum += ink
            if ink > 3:
                nz += 1
    print(f"  段{k}: 有墨码位 {nz:>5} / 2816   平均墨 {inksum/2816:.1f}")
    print(f"        高度分布 {dict(sorted(hc.items())[:8])}")

# 具体看码 0x000 的 4 段
print("\n=== 码 0x000 的 4 段原始数据 ===")
o = PAGES4[0] - BASE
b = zh[o:o + 64]
for k in range(4):
    src = b[k * 16:(k + 1) * 16]
    d = decode16(src)
    h, w, ink = seg_stats(d)
    print(f"\n  段{k} 源={src.hex(' ')}  高={h} 宽={w} 墨={ink}")
    m = nibs(d)
    for y in range(8):
        print("    " + "".join("#" if v == 12 else ("+" if v == 11 else ".")
                               for v in m[y]))
