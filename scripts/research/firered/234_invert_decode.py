"""调研(234) 反转 decode16，从小字字形反推 ROM 源字节。

═══ 原理 ═══
decode16 @ 0x08002F5C（已确证）：
    for r3 in 0..15:
        v = src[(r3//2)*2]        if r3 奇
        v = src[(r3//2)*2 + 1]    if r3 偶      （即 src[1],src[0],src[3],src[2]...）
        out[2*r3 : 2*r3+2] = PAL[ IDX[v] ]

⇒ 已知 out（32 字节小字）和 PAL / IDX，可以**反解出 src（16 字节）**：
   对每个 r3：
       pair = out[2*r3 : 2*r3+2]
       idx  = PAL 反查表[pair]
       若 IDX 是单射，则 v = IDX 反查表[idx]
   ⇒ 得到 16 个 v，按「奇数位/偶数位」还原成 16 字节 src
   ⇒ 然后在 ROM 里搜这 16 字节 → 找到字库位置

═══ 为什么这样能成 ═══
之前直接搜 32B 小字永远 0 命中，因为 ROM 里存的是**索引 v**，
不是像素；经过 IDX→PAL 两级映射才变成像素。

用法：python scripts/research/firered/234_invert_decode.py
"""
from __future__ import annotations

import struct
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
P = ROOT / "work" / "_probe" / "party232"
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
ew = (P / "s05_party_ewram.bin").read_bytes()
iw = (P / "s05_party_iwram.bin").read_bytes()
BASE = 0x08000000

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = iw[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

print("=== 基本表 ===")
print(f"IDX 前 32: {list(IDX[:32])}")
print(f"IDX 值域: {min(IDX)}..{max(IDX)}")
print(f"PAL 前 32B: {PAL[:32].hex(' ')}")

# ── 建反查表 ──────────────────────────────────────────────
# PAL 反查：2 字节 -> 索引
pal_inv = {}
for k in range(max(IDX) + 1):
    pair = PAL[k * 2:k * 2 + 2]
    if len(pair) == 2 and pair not in pal_inv:
        pal_inv[pair] = k

# IDX 反查：索引 -> 字节值（可能多对一，保留全部）
idx_inv = defaultdict(list)
for v in range(256):
    idx_inv[IDX[v]].append(v)

print(f"\nPAL 反查表大小: {len(pal_inv)}")
print(f"IDX 反查表大小: {len(idx_inv)}")

# ── 取小字目标 ────────────────────────────────────────────
def nibs(b):
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = b[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


# EWRAM 0x02001F00 处的两个块拼成 8x16，但小字本身就是 8x8
targets = {}
for addr in (0x02001F00, 0x02002890, 0x02003D00):
    o = addr - 0x02000000
    targets[addr] = ew[o:o + 32]

print("\n=== 目标小字（32B）===")
for a, b in targets.items():
    m = nibs(b)
    txt = (m == 11) | (m == 12)
    print(f"\n0x{a:08X}  墨={int(txt.sum())}  {b[:12].hex()}")
    for y in range(8):
        print("  " + "".join("#" if v == 12 else ("+" if v == 11 else ".")
                             for v in m[y]))


def invert(target32: bytes) -> list[bytes]:
    """从 32B 输出反解 16B 源（返回所有可能组合）。"""
    vs = []   # 16 个 v 值（按 out 顺序）
    for r3 in range(16):
        pair = target32[r3 * 2:r3 * 2 + 2]
        idx = pal_inv.get(pair)
        if idx is None:
            return []          # 该像素不在 PAL 里 → 不能用同一套表
        cands = idx_inv.get(idx)
        if not cands:
            return []
        vs.append(cands)

    # 每个位置可能有多个候选；只取第一个（IDX 多数是单射）
    v0 = [c[0] for c in vs]

    # 还原成 src：r3 偶 -> src[p+1]；r3 奇 -> src[p]
    src = bytearray(16)
    for r3 in range(16):
        p = (r3 // 2) * 2
        if r3 % 2 == 0:
            src[p + 1] = v0[r3]
        else:
            src[p] = v0[r3]
    return [bytes(src)]


print("\n\n=== 反解结果 & 在 ROM 里搜 ===")
for a, b in targets.items():
    srcs = invert(b)
    if not srcs:
        print(f"\n0x{a:08X}: ✘ 无法反解（像素不在 PAL 表内）")
        # 诊断：看有多少像素对在 PAL 里
        cnt = 0
        for r3 in range(16):
            if b[r3 * 2:r3 * 2 + 2] in pal_inv:
                cnt += 1
        print(f"  32B 中 {cnt}/16 对能在 PAL 里找到")
        continue
    for s in srcs:
        print(f"\n0x{a:08X}: 反解源 16B = {s.hex(' ')}")
        p = zh.find(s)
        n = 0
        pos = []
        while p >= 0 and n < 8:
            pos.append(BASE + p)
            n += 1
            p = zh.find(s, p + 1)
        print(f"  汉化 ROM 命中 {n} 处: {[hex(x) for x in pos]}")
        p = ja.find(s)
        print(f"  原版 ROM 命中: {'0x%08X' % (BASE + p) if p >= 0 else '-'}")
