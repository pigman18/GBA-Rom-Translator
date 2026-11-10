"""验证：小字用第二张 IDX 表 @0x081CE000。

═══ 240 的关键发现 ═══
全 ROM 搜主 IDX 前 32B，命中**两处**：
    0x081CDF40   ← 主字库用的
    0x081CE000   ← 另一张！

两个地址差 0xC0，说明是两张独立的索引表（每张 0xC0=192 字节？）。
小字极可能用第二张。

本脚本：
 ① dump 两张 IDX 表，对比异同
 ② 用 IDX2 反解小字：v -> IDX2[v] -> PAL -> 像素
 ③ 若 IDX2 能让小字对上 PAL，就找到了
 ④ 找两张表各自对应的页表 / 调用点
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
BASE = 0x08000000

IDX1 = 0x081CDF40
IDX2 = 0x081CE000

print("=== 两张 IDX 表对比 ===")
for name, addr in (("IDX1", IDX1), ("IDX2", IDX2)):
    o = addr - BASE
    seg = zh[o:o + 64]
    jseg = ja[o:o + 64]
    print(f"\n  {name} @0x{addr:08X}:")
    for i in range(0, 64, 16):
        print(f"    +{i:03X}  {seg[i:i+16].hex(' ')}")
    print(f"    原版: {jseg[:32].hex(' ')}")
    print(f"    汉化与原版相同: {seg == jseg}")

print("\n=== 两表是否内容相同 ===")
s1 = zh[IDX1 - BASE:IDX1 - BASE + 256]
s2 = zh[IDX2 - BASE:IDX2 - BASE + 256]
same = sum(1 for a, b in zip(s1, s2) if a == b)
print(f"  256 字节中相同 {same}")
print(f"  完全一致: {s1 == s2}")

# 差异位置
diffs = [(i, s1[i], s2[i]) for i in range(256) if s1[i] != s2[i]]
print(f"  差异 {len(diffs)} 处，前 20: {diffs[:20]}")

# ── 谁引用这两张表 ────────────────────────────────────────
print("\n=== 谁引用 IDX1 / IDX2 ===")
for name, addr in (("IDX1", IDX1), ("IDX2", IDX2)):
    nd = struct.pack('<I', addr)
    pos = zh.find(nd)
    hits = []
    while pos >= 0:
        hits.append(BASE + pos)
        pos = zh.find(nd, pos + 1)
    print(f"  {name} 0x{addr:08X}: {len(hits)} 处 -> {[hex(h) for h in hits[:8]]}")

# ── 用 IDX2 试解小字 ──────────────────────────────────────
P = ROOT / "work" / "_probe" / "party232"
vr = (P / "s05_party_vram.bin").read_bytes()
iw = (P / "s05_party_iwram.bin").read_bytes()
PAL = iw[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

print("\n=== PAL(party232) 值域 ===")
print(f"  前 32B: {PAL[:32].hex(' ')}")

# PAL 里所有不同的 2 字节值
pal_vals = set()
for k in range(256):
    pal_vals.add(PAL[k * 2:k * 2 + 2])
print(f"  PAL 中不同 2 字节值: {len(pal_vals)}")
print(f"  有 1111 吗: {b'\x11\x11' in pal_vals}")
print(f"  有 bb4c 吗: {b'\xbb\x4c' in pal_vals}")

# 小字 tile 的字节对是否都在 PAL 里
print("\n=== 小字字节对 vs PAL ===")
for t in (137, 213, 267, 321, 375):
    b = vr[t * 32:t * 32 + 32]
    inp = sum(1 for k in range(0, 32, 2) if b[k:k + 2] in pal_vals)
    print(f"  tile {t}: {inp}/16 对在 PAL 里")

# 小字用的可能不是 0x03000A40，而是别的 PAL
print("\n=== 在 IWRAM 里找包含 bb4c / 1111 的 2 字节表 ===")
need = {b'\xbb\x4c', b'\x11\x11', b'\xb4\xbc', b'\xcc\x5c'}
for k in range(0, len(iw) - 2, 2):
    seg = iw[k:k + 64]
    hit = sum(1 for j in range(0, len(seg) - 1, 2) if seg[j:j + 2] in need)
    if hit >= 3:
        print(f"  0x{0x03000000 + k:08X} 命中 {hit}  {iw[k:k+16].hex(' ')}")
        break
else:
    print("  IWRAM 里没找到")
