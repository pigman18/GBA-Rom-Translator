"""验证：小字 = 主字库同一套 PAGES4 的**单个 16B 段**解码结果。

═══ 235 的关键发现 ═══
IWRAM 0x03003DE0（主字库解码缓冲）里包含了小字 tile 的全部字节对（30/32 命中）。
⇒ 小字与大字**共用 id="IDX/PAL/解码函数**，区别只在「每字解 1 段还是 4 段」。

即：
  大字：addr = PAGES4[hi] + lo*64，解 4 段 -> 4 个 tile -> 16x16（有效 12x16）
  小字：addr = PAGES4[hi] + lo*64，解 1 段 -> 1 个 tile -> 8x8

本脚本：对每个码位的**每一段**做 decode16，与 VRAM 里的小字比对。
若命中 → 小字就是主字库的第 k 段，字库本来就有，不需要另找。

用法：python scripts/research/firered/236_small_is_main.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
P = ROOT / "work" / "_probe" / "party232"
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
iw = (P / "s05_party_iwram.bin").read_bytes()
vr = (P / "s05_party_vram.bin").read_bytes()
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
        if r3 & 1:
            v = src[p] if p < len(src) else 0
        else:
            v = src[p + 1] if p + 1 < len(src) else 0
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


# 目标：VRAM 里确认的小字 tile
targets = {}
for t in (137, 213, 267, 321, 375):
    targets[t] = vr[t * 32:t * 32 + 32]

print("=== 全码位 × 4 段 扫描，找匹配 ===")
hits = []
for hi, pg in enumerate(PAGES4):
    for lo in range(256):
        o = pg + lo * 64 - BASE
        if o < 0 or o + 64 > len(zh):
            continue
        b = zh[o:o + 64]
        for k in range(4):
            d = decode16(b[k * 16:(k + 1) * 16])
            for t, tgt in targets.items():
                if d == tgt:
                    hits.append((t, hi * 256 + lo, k))
print(f"命中 {len(hits)} 个：")
for t, code, k in hits:
    print(f"  VRAM tile {t} == 码 0x{code:03X} 的第 {k} 段")

if not hits:
    print("  0 命中 —— 小字不是主字库的解码结果")
    # 退一步：找最接近的
    print("\n=== 找最接近的（字节相同数）===")
    for t, tgt in list(targets.items())[:2]:
        best = []
        for hi, pg in enumerate(PAGES4):
            for lo in range(256):
                o = pg + lo * 64 - BASE
                if o < 0 or o + 64 > len(zh):
                    continue
                b = zh[o:o + 64]
                for k in range(4):
                    d = decode16(b[k * 16:(k + 1) * 16])
                    same = sum(1 for x, y in zip(d, tgt) if x == y)
                    best.append((same, hi * 256 + lo, k))
        best.sort(reverse=True)
        print(f"  tile {t}: 最接近 {[(s, hex(c), k) for s, c, k in best[:4]]}")

# 反向验证：Z 主字库每个码位的第 0 段，有多少是"6~8 高"的小字形状
print("\n=== 主字库第 0 段的字形高度分布（若小字来自这里，应大量 6~8）===")
from collections import Counter
hc = Counter()
sample = []
for hi, pg in enumerate(PAGES4):
    for lo in range(0, 256):
        o = pg + lo * 64 - BASE
        if o < 0 or o + 64 > len(zh):
            continue
        d = decode16(zh[o:o + 16])
        m = nibs(d)
        txt = (m == 11) | (m == 12)
        ys = np.flatnonzero(txt.any(axis=1))
        hc[len(ys)] += 1
        if len(ys) and len(sample) < 5:
            sample.append((hi * 256 + lo, m))
print(f"  {dict(sorted(hc.items()))}")

for code, m in sample:
    print(f"\n  码 0x{code:03X} 第0段:")
    for y in range(8):
        print("    " + "".join("#" if v == 12 else ("+" if v == 11 else ".")
                               for v in m[y]))
