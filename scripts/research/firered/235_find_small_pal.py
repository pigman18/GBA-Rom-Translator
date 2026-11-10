"""找小字的 PAL 表和 IDX 表 —— 与主字库不同的另一套。

═══ 234 的发现 ═══
主字库的 PAL @0x03000A40 是 `11 11 / 11 21 / 11 31 / 11 12 ...`，
而小字像素是 `55 55 55... bb cb 55` 这样的值，完全不在那张表里。

⇒ 小字有**自己的一套 (IDX, PAL)**。

【怎么找】
小字缓冲在 EWRAM 里（如 0x02001F00）。渲染时同样走
      v -> IDX2[v] -> PAL2[idx] -> 2 字节
那么 PAL2 必然也在 IWRAM/EWRAM 里，且内容会包含小字里出现的字节对。

小字里出现的字节对（从 32B 目标统计）：去重后是一小组。
⇒ 在 IWRAM/EWRAM 里搜「这些字节对连续出现」的表。

用法：python scripts/research/firered/235_find_small_pal.py
"""
from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
P = ROOT / "work" / "_probe" / "party232"
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ew = (P / "s05_party_ewram.bin").read_bytes()
iw = (P / "s05_party_iwram.bin").read_bytes()
vr = (P / "s05_party_vram.bin").read_bytes()
BASE = 0x08000000

# 小字目标（VRAM 里已确认的 5 个）
SMALL_TILES = [137, 213, 267, 321, 375, 137 + 0]
targets = []
for t in (137, 213, 267, 321, 375):
    o = t * 32
    if o + 32 <= len(vr):
        targets.append((t, vr[o:o + 32]))

print("=== 小字 tile 的字节对统计 ===")
pairs = Counter()
for t, b in targets:
    print(f"\n  tile {t}: {b.hex(' ')}")
    for k in range(0, 32, 2):
        pairs[b[k:k + 2]] += 1
print(f"\n  出现的字节对（{len(pairs)} 种）:")
for p, n in pairs.most_common(20):
    print(f"    {p.hex()} x{n}")

# ── 在 IWRAM/EWRAM 里找「包含这些字节对的连续表」─────────────
print("\n=== 在 IWRAM 里找含这些字节对的 2 字节表 ===")
need = set(pairs)
best = []
for k in range(0, len(iw) - 2, 2):
    seg = iw[k:k + 200]
    hit = sum(1 for j in range(0, len(seg) - 1, 2) if seg[j:j + 2] in need)
    if hit >= 5:
        best.append((hit, 0x03000000 + k))
best.sort(reverse=True)
print(f"  IWRAM 候选 {len(best)} 个，前 10:")
for hit, a in best[:10]:
    print(f"    0x{a:08X}  命中 {hit}")

print("\n=== 在 EWRAM 里找 ===")
best2 = []
for k in range(0, len(ew) - 2, 2):
    seg = ew[k:k + 200]
    hit = sum(1 for j in range(0, len(seg) - 1, 2) if seg[j:j + 2] in need)
    if hit >= 8:
        best2.append((hit, 0x02000000 + k))
best2.sort(reverse=True)
print(f"  EWRAM 候选 {len(best2)} 个，前 10:")
for hit, a in best2[:10]:
    print(f"    0x{a:08X}  命中 {hit}")

# ── 直接看主 PAL 表附近的其它表 ────────────────────────────
print("\n=== IWRAM 0x03000900..0x03000C00 区域（主 PAL 前后）===")
o = 0x03000900 - 0x03000000
for i in range(0, 0x300, 16):
    seg = iw[o + i:o + i + 16]
    mark = "  <-- 主PAL" if 0x03000A40 - 0x03000000 == o + i else ""
    print(f"  0x{0x03000900 + i:08X}  {seg.hex(' ')}{mark}")
