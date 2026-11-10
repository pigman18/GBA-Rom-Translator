"""找小字的调色板：小字的字节对 (bb4c / b4bc / cc5c ...) 在哪张表里。

═══ 241 的结论 ═══
· IDX1 只有 1 处引用（0x08002F78，主字库解码函数）→ 主字库专用
· IDX2 0 处引用 → 废弃/冗余
· 小字字节对在 party232 的 PAL(0x03000A40) 里只有 2/16 → 用的不是这张

⇒ 小字有自己的调色板表，内容应包含 bb4c / b4bc / cc5c / 8888 / 1111 等。

【思路】
小字的像素值有明确规律：出现 1/4/5/8/b/c 等 nibble，
说明调色板项是 (低位 4bit, 高位 4bit) 的组合，形如 `b4 4c`。
⇒ 在 IWRAM 全量、EWRAM 全量、以及 VRAM 调色板区(0x05000000)里找。

同时：小字很可能是**原版就有的 8x8 字体**（ASCII/假名那套）被汉化扩展，
所以找原版 ROM 里也存在的调色板表。

用法：python scripts/research/firered/242_find_small_palette.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
P = ROOT / "work" / "_probe" / "party232"
vr = (P / "s05_party_vram.bin").read_bytes()
ew = (P / "s05_party_ewram.bin").read_bytes()
iw = (P / "s05_party_iwram.bin").read_bytes()
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
BASE = 0x08000000

SMALL = [137, 213, 267, 321, 375]
need = set()
for t in SMALL:
    b = vr[t * 32:t * 32 + 32]
    for k in range(0, 32, 2):
        need.add(b[k:k + 2])
print(f"小字字节对 {len(need)} 种:")
print("  " + " ".join(sorted(p.hex() for p in need)))

# ── 在 IWRAM / EWRAM 全量搜：哪个偏移开始，连续出现这些字节对最多 ──
def scan(buf, base, label, window=512, minhit=6):
    best = []
    for k in range(0, len(buf) - 2, 2):
        seg = buf[k:k + window]
        hit = 0
        details = []
        for j in range(0, len(seg) - 1, 2):
            if seg[j:j + 2] in need:
                hit += 1
                details.append(j // 2)
        if hit >= minhit:
            best.append((hit, base + k, details[:8]))
    best.sort(reverse=True)
    print(f"\n=== {label}: 命中>= {minhit} 的窗口 {len(best)} 个，前 8 ===")
    for hit, a, det in best[:8]:
        print(f"  0x{a:08X}  命中 {hit}  位置 {det}")
        print(f"    内容: {buf[a - base:a - base + 32].hex(' ')}")
    return best


b_iw = scan(iw, 0x03000000, "IWRAM", 512, 8)
b_ew = scan(ew, 0x02000000, "EWRAM", 512, 10)

# ── 直接定位小字字模所在的表：找 tile 137 的 32B 在哪个「表」里 ──
print("\n\n=== 小字字模在 EWRAM 的上下文 ===")
tgt = vr[137 * 32:137 * 32 + 32]
p = ew.find(tgt)
print(f"  tile 137 的 32B 在 EWRAM: {'0x%08X' % (0x02000000 + p) if p >= 0 else '-'}")
if p >= 0:
    o = p
    print(f"  上下文 96B（前 32 / 本块 / 后 32）:")
    for k in (-32, 0, 32):
        seg = ew[o + k:o + k + 32]
        print(f"    {k:+4d}: {seg.hex(' ')}")

# ── 小字块之间的间隔规律 ──
print("\n=== 小字块在 EWRAM 的地址与间隔 ===")
addrs = []
for t in SMALL:
    blob = vr[t * 32:t * 32 + 32]
    q = ew.find(blob)
    if q >= 0:
        addrs.append((t, 0x02000000 + q))
for t, a in addrs:
    print(f"  tile {t} -> EWRAM 0x{a:08X}")
if len(addrs) > 1:
    ds = [addrs[i + 1][1] - addrs[i][1] for i in range(len(addrs) - 1)]
    print(f"  间隔: {ds}")

# ── 关键：小字是否直接来自原版 ROM 的 8x8 字体（1bpp 或 2bpp）──
print("\n\n=== 小字是否为原版 8x8 字体的扩展（搜原版）===")
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
for t in SMALL[:3]:
    blob = vr[t * 32:t * 32 + 32]
    pe = zh.find(blob)
    pj = ja.find(blob)
    print(f"  tile {t}: 汉化={'0x%08X' % (BASE + pe) if pe >= 0 else '-'}  "
          f"原版={'0x%08X' % (BASE + pj) if pj >= 0 else '-'}")

# 小字的 nibble 值域（判断是 4bpp 还是别的）
print("\n=== 小字 nibble 值域 ===")
c = Counter()
for t in SMALL:
    for b in vr[t * 32:t * 32 + 32]:
        c[b & 0xF] += 1
        c[b >> 4] += 1
print(f"  {dict(sorted(c.items()))}")
