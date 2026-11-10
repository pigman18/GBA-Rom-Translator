"""调研(293) 验证：小字 = 大字缩小。

═══ 支持这个假设的证据 ═══
1. 小字页表 0x08B74000 和大字页表 0x089D08A0 都是 11 页、原版 100% FF
2. 两套都走同一个 decode16 / IDX / PAL
3. 大小字的码位顺序完全一致（都是「中 文 宝 可 梦 盘…」）
4. 小字 VRAM tile 是 7-8 高、5-8 宽，正好是大字 10-12 宽 12 高的 2/3
5. EWRAM 那块缓冲只是 charBase 镜像，不是独立字库

⇒ 假设：小字 = 大字位图**水平压缩**（16 列 -> 8 列，取左 8 或隔列采样）

本脚本：把大字 16x16 按几种方式缩到 8 宽，与 VRAM 真实小字 tile 比对。
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
P = ROOT / "work" / "_probe" / "party261"
vr = (P / "s01_party01_vram.bin").read_bytes()
iw = (P / "s01_party01_iwram.bin").read_bytes()
IW205 = (ROOT / "work/_probe/runtime205/t000_prove_iwram.bin").read_bytes()
BASE = 0x08000000
N = len(zh)

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = iw[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]
PAL205 = IW205[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

MAIN = [0x089C4230, 0x089555A0, 0x08B55564, 0x08A2725C, 0x08B333A0,
        0x08907C0C, 0x08AD690C, 0x08935A08, 0x08A72610, 0x08AB5404,
        0x089B2B0C]
SMALL = [0x08B01000, 0x08B40000, 0x08B50000, 0x08B60000, 0x08B70000,
         0x08B80000, 0x08B90000, 0x08BA0000, 0x08BB0000,
         0x08B64000, 0x08B68000]


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
    if hi >= len(MAIN):
        return None
    o = MAIN[hi] + lo * 64 - BASE
    if o < 0 or o + 0x120 > N:
        return None
    s = [mat8(decode16(zh[o + k:o + k + 16], PAL205))
         for k in (0x00, 0x10, 0x20, 0x30)]
    return np.vstack([np.hstack([s[0], s[1]]), np.hstack([s[2], s[3]])])


def small(code):
    """小字页表 + (lo>>3)*512 + (code&7)*32，4 段 2x2。"""
    hi, lo = code >> 8, code & 0xFF
    if hi >= len(SMALL):
        return None
    a = SMALL[hi] + (lo >> 3) * 512 + (code & 7) * 32
    o = a - BASE
    if o < 0 or o + 0x120 > N:
        return None
    s = [mat8(decode16(zh[o + k:o + k + 16], PAL))
         for k in (0x00, 0x10, 0x100, 0x110)]
    return np.vstack([np.hstack([s[0], s[1]]), np.hstack([s[2], s[3]])])


def to_mask(m, bg):
    return (m != bg).astype(np.uint8)


def shrink(mask, mode):
    """16x16 -> 8x16（只压水平）。"""
    if mode == "left8":
        return mask[:, :8]
    if mode == "right8":
        return mask[:, 8:]
    if mode == "every2":
        return mask[:, ::2]
    if mode == "or2":
        return (mask[:, 0::2] | mask[:, 1::2])
    if mode == "and2":
        return (mask[:, 0::2] & mask[:, 1::2])
    return mask[:, :8]


print("=== 比较：大字缩小后 vs 小字页表解出的字（码 0x000..0x00F）===")
for mode in ("left8", "right8", "every2", "or2", "and2"):
    same_total = 0
    total = 0
    for code in range(16):
        b = big(code)
        s = small(code)
        if b is None or s is None:
            continue
        bgb = Counter(int(v) for v in b.flatten()).most_common(1)[0][0]
        bgs = Counter(int(v) for v in s.flatten()).most_common(1)[0][0]
        mb = to_mask(b, bgb)
        ms = to_mask(s, bgs)
        shr = shrink(mb, mode)
        ms2 = ms[:, :8]
        same = int((shr == ms2).sum())
        same_total += same
        total += shr.size
    if total:
        print(f"  {mode:<8} 像素一致率 {same_total / total:.1%}")

# 也看：不缩小，大字左 8 列直接比小字的左 8 列
print("\n=== 大字 / 小字 的实际墨迹 bbox ===")
for code in range(4):
    b = big(code)
    s = small(code)
    if b is None or s is None:
        continue
    bgb = Counter(int(v) for v in b.flatten()).most_common(1)[0][0]
    bgs = Counter(int(v) for v in s.flatten()).most_common(1)[0][0]
    nb = np.argwhere(b != bgb)
    ns = np.argwhere(s != bgs)
    print(f"  码 0x{code:03X}: 大字 bbox x={nb[:,1].min()}..{nb[:,1].max()} "
          f"y={nb[:,0].min()}..{nb[:,0].max()}  |  "
          f"小字 bbox x={ns[:,1].min()}..{ns[:,1].max()} "
          f"y={ns[:,0].min()}..{ns[:,0].max()}")

print("\n=== 直接看图：大字 vs 小字（码 0x000）===")
b = big(0)
s = small(0)
if b is not None and s is not None:
    bgb = Counter(int(v) for v in b.flatten()).most_common(1)[0][0]
    bgs = Counter(int(v) for v in s.flatten()).most_common(1)[0][0]
    print("  大字 16x16          小字 16x16")
    for y in range(16):
        lb = "".join("." if v == bgb else "#" for v in b[y])
        ls = "".join("." if v == bgs else "#" for v in s[y])
        print(f"  {lb}    {ls}")
