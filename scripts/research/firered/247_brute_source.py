"""穷举 IDX 反查的所有组合，找出 ROM 里真实存在的 16B 源。

═══ 246 的进展 ═══
0x03003DE0 的 32B 全部 16 个像素对都在 party232 的 PAL 里 ⇒ 确认是解码输出。
但按 IDX 反查选第一个候选，得到的 16B 源在 ROM 里搜不到。

原因：IDX 是**多对一**（如 IDX[0]=0, IDX[3]=0, IDX[12]=0 ...），
反查时每个 k 可能有多个 v 候选。

本脚本：对每个 k 取全部候选 v，做笛卡尔积（限制规模），
所有候选源都去 ROM 搜，找到真实存在的那个。
"""
from __future__ import annotations

import itertools
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
iw = (ROOT / "work/_probe/party232/s05_party_iwram.bin").read_bytes()
BASE = 0x08000000

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = iw[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

pal2idx = {}
for k in range(256):
    pair = PAL[k * 2:k * 2 + 2]
    if len(pair) == 2 and pair not in pal2idx:
        pal2idx[pair] = k

idx2v = defaultdict(list)
for v in range(256):
    idx2v[IDX[v]].append(v)

buf = iw[0x03003DE0 - 0x03000000:0x03003DE0 - 0x03000000 + 32]
ks = []
for r3 in range(16):
    ks.append(pal2idx[buf[r3 * 2:r3 * 2 + 2]])
print(f"索引序列: {ks}")

print("\n=== 每个索引的 v 候选数 ===")
cands = []
for k in ks:
    c = idx2v.get(k, [])
    cands.append(c)
    print(f"  idx {k:>3}: {len(c)} 个候选 {c[:6]}")

total = 1
for c in cands:
    total *= max(1, len(c))
print(f"\n组合总数: {total:,}")

# 限制：只对候选数 <=4 的做完整穷举；候选多的取前 4
cands2 = [c[:4] if len(c) > 4 else c for c in cands]
total2 = 1
for c in cands2:
    total2 *= max(1, len(c))
print(f"裁剪后组合数: {total2:,}")

found = []
if total2 <= 200000:
    for combo in itertools.product(*cands2):
        src = bytearray(16)
        for r3 in range(16):
            p = (r3 // 2) * 2
            v = combo[r3]
            if r3 % 2 == 0:
                src[p + 1] = v
            else:
                src[p] = v
        s = bytes(src)
        p = zh.find(s)
        if p >= 0:
            found.append((s, BASE + p, "汉化"))
        p = ja.find(s)
        if p >= 0:
            found.append((s, BASE + p, "原版"))
    print(f"\n命中 {len(found)}:")
    for s, a, which in found[:20]:
        print(f"  {s.hex(' ')} -> {which} 0x{a:08X}")
else:
    print("  组合过多，改为逐字节贪婪搜索")

if not found:
    print("\n=== 改法：不要求 16B 全对，搜 8B 片段 ===")
    # 用前半 8 字节
    for n in (8, 12, 16):
        c2 = [c[:2] if len(c) > 2 else c for c in cands[:n]]
        cnt = 0
        for combo in itertools.product(*c2):
            src = bytearray(16)
            for r3, v in enumerate(combo):
                p = (r3 // 2) * 2
                if r3 % 2 == 0:
                    src[p + 1] = v
                else:
                    src[p] = v
            if zh.find(bytes(src[:n])) >= 0:
                cnt += 1
        if cnt:
            print(f"  前 {n} 字节命中 {cnt} 次")
            break

# 另一个方向：小字可能用的是**另一张 IDX**（已知 0x081CE000 也存在）
print("\n=== 用 IDX2 @0x081CE000 试 ===")
IDX2 = zh[0x081CE000 - BASE:0x081CE000 - BASE + 256]
idx2v2 = defaultdict(list)
for v in range(256):
    idx2v2[IDX2[v]].append(v)
cands_b = [idx2v2.get(k, [])[:4] for k in ks]
print(f"  候选数: {[len(c) for c in cands_b]}")
f2 = []
for combo in itertools.product(*cands_b):
    src = bytearray(16)
    for r3, v in enumerate(combo):
        p = (r3 // 2) * 2
        if r3 % 2 == 0:
            src[p + 1] = v
        else:
            src[p] = v
    s = bytes(src)
    if zh.find(s) >= 0:
        f2.append((s, BASE + zh.find(s)))
print(f"  IDX2 命中 {len(f2)}: {[(s.hex(), hex(a)) for s, a in f2[:6]]}")
