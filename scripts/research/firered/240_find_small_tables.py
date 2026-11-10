"""从小字缓冲反向追：找写它的代码，从而找到字库表。

═══ 现状 ═══
· 小字 32B 块在 EWRAM（0x02001F00 等），VRAM tile 137 有同样的 32B
· ROM 里直接搜 0 命中
· 主字库 PAGES4 解不出
· 主字库 WIDTH 只有 0x0A/0x0C 两档，没有小字的尺寸

⇒ 小字**必然有自己的（页表 + IDX + PAL）**，且这套表在 ROM 里。

【本脚本的新思路：对比 IDX 表】
主字库用 IDX @0x081CDF40。
小字若走同一解码函数，也读 IDX @0x081CDF40（那是个硬编码常量）。
但如果小字有独立的解码函数，就会读别的 IDX 表。

⇒ 在 ROM 里找「和 0x081CDF40 结构相似的表」（0,1,2,0,3,4,5,3,...）
   以及找「页表结构相似的表」（一串 ROM 指针，11 项左右）

用法：python scripts/research/firered/240_find_small_tables.py
"""
from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
BASE = 0x08000000
N = len(zh)

# ── 1) 找和主 IDX 相似的表 ────────────────────────────────
IDX0 = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 32]
print(f"=== 主 IDX 前 32B: {IDX0.hex(' ')} ===")
print("=== 全 ROM 搜完全相同前缀 ===")
pos = zh.find(IDX0)
hits = []
while pos >= 0:
    hits.append(BASE + pos)
    pos = zh.find(IDX0, pos + 1)
print(f"  命中 {len(hits)}: {[hex(h) for h in hits]}")

# ── 2) 找页表：11~16 个连续的 ROM 指针 ────────────────────
print("\n=== 找「连续 ROM 指针表」（页表特征）===")
PTR_MIN = 8
found = []
i = 0
while i < N - 4 * PTR_MIN:
    v = struct.unpack_from('<I', zh, i)[0]
    if not (BASE <= v < BASE + N):
        i += 4
        continue
    # 数连续指针
    cnt = 0
    j = i
    vals = []
    while j < N - 4:
        v2 = struct.unpack_from('<I', zh, j)[0]
        if BASE <= v2 < BASE + N:
            vals.append(v2)
            cnt += 1
            j += 4
        else:
            break
    if cnt >= PTR_MIN:
        # 检查这些指针指向的区是否「原版 FF、汉化有内容」
        added = 0
        for v2 in vals[:16]:
            o = v2 - BASE
            if 0 <= o < N - 64:
                added += sum(1 for a, b in zip(zh[o:o + 64], ja[o:o + 64])
                             if b == 0xFF and a != 0xFF)
        found.append((cnt, BASE + i, added, vals[:12]))
    i += max(4, cnt * 4)

found.sort(key=lambda t: (-t[2], -t[0]))
print(f"  候选页表 {len(found)} 个，前 15（按指向区新增字节排序）:")
for cnt, addr, added, vals in found[:15]:
    print(f"    0x{addr:08X}  {cnt} 项  指向区新增={added}")
    print(f"      {[hex(v) for v in vals[:8]]}")

# ── 3) 主字库页表是否为其中之一 ───────────────────────────
print("\n=== 主字库页表 0x089D08A0 是否在候选里 ===")
for cnt, addr, added, vals in found[:80]:
    if addr == 0x089D08A0:
        print(f"  是：{cnt} 项，指向区新增={added}")
        break
else:
    print("  不在前 80（可能因为它的指针目标在原版 FF 区，added 计算方式不同）")

# ── 4) 小字 tile 的字节对，在 ROM 全量搜「哪个区含大量相同字节对」──
print("\n=== 小字字节对在 ROM 里的富集区 ===")
vr = (ROOT / "work/_probe/party232/s05_party_vram.bin").read_bytes()
small_pairs = set()
for t in (137, 213, 267, 321, 375):
    b = vr[t * 32:t * 32 + 32]
    for k in range(0, 32, 2):
        small_pairs.add(b[k:k + 2])
print(f"  小字字节对 {len(small_pairs)} 种: {[p.hex() for p in list(small_pairs)[:10]]}")

W = 0x4000
scores = []
for off in range(0, N - W, W):
    seg = zh[off:off + W]
    cnt = 0
    for k in range(0, W - 1, 2):
        if seg[k:k + 2] in small_pairs:
            cnt += 1
    scores.append((cnt, off))
scores.sort(reverse=True)
print(f"  按字节对命中数排序，前 12:")
for cnt, off in scores[:12]:
    print(f"    0x{BASE + off:08X}  命中 {cnt} 对")
