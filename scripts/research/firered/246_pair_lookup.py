"""关键修正：小字的输出值域是 0x11/0x21/0x22/0x33，对应 PAL 里的项。

═══ 245 的教训 ═══
我用「整个字节对相等」去比对，但小字输出里有两字节的**像素对**关系。

IWRAM 0x03003DE0 = `11 11 11 11 11 21 13 21 22 22 22 22 33 23 33 23 ...`
party232 PAL[:16] = `11 11 | 11 21 | 11 31 | 11 12 | 11 22 | 11 32 | 11 13 | 11 23`

⇒ PAL 项是 (左像素, 右像素) 两字节，如 `11 21` 表示 (0x11, 0x21)。
   而缓冲 `11 21` 正好等于 PAL[1]！

本脚本：
 ① 把缓冲按 2 字节切，找出每个 pair == PAL[k*2:k*2+2] 的 k
 ② 由 k 反查 IDX（IDX 是 idx -> value 的逆映射：IDX[v]=k）
 ③ 得到 v 序列 -> 还原 16 字节源
 ④ 在 ROM 里搜这个源，定位小字字库
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
iw = (ROOT / "work/_probe/party232/s05_party_iwram.bin").read_bytes()
vr = (ROOT / "work/_probe/party232/s05_party_vram.bin").read_bytes()
BASE = 0x08000000

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = iw[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

print("=== PAL 前 16 项（2 字节一项）===")
for k in range(16):
    print(f"  PAL[{k:2d}] = {PAL[k*2]:02x} {PAL[k*2+1]:02x}")

# PAL 项 -> 索引
pal2idx = {}
for k in range(256):
    pair = PAL[k * 2:k * 2 + 2]
    if len(pair) == 2 and pair not in pal2idx:
        pal2idx[pair] = k

# 目标：IWRAM 缓冲
buf = iw[0x03003DE0 - 0x03000000:0x03003DE0 - 0x03000000 + 32]
print(f"\n=== 目标缓冲 32B: {buf.hex(' ')} ===")

print("\n=== 逐像素对反查 PAL ===")
ks = []
ok = True
for r3 in range(16):
    pair = buf[r3 * 2:r3 * 2 + 2]
    k = pal2idx.get(pair)
    mark = f"idx={k}" if k is not None else "✘不在PAL"
    print(f"  [{r3:2d}] {pair.hex()}  {mark}")
    if k is None:
        ok = False
    ks.append(k)

if not ok:
    print("\n  有像素对不在 PAL 里 → 这张 PAL 仍不匹配")
    # 统计缓冲里所有出现的 2 字节对
    from collections import Counter
    c = Counter(buf[k:k + 2] for k in range(0, 32, 2))
    print(f"  缓冲中的像素对: {[(p.hex(), n) for p, n in c.most_common(12)]}")
    print(f"  PAL 里的项数: {len(pal2idx)}")
else:
    print(f"\n  全部命中！索引序列: {ks}")
    # 反查 IDX：IDX[v] = k  =>  v
    idx2v = {}
    for v in range(256):
        idx2v.setdefault(IDX[v], []).append(v)
    vs = []
    for k in ks:
        cands = idx2v.get(k, [])
        vs.append(cands[0] if cands else 0)
    print(f"  v 序列: {vs}")
    # 还原源：r3 偶 -> src[p+1]，r3 奇 -> src[p]
    src = bytearray(16)
    for r3 in range(16):
        p = (r3 // 2) * 2
        if r3 % 2 == 0:
            src[p + 1] = vs[r3]
        else:
            src[p] = vs[r3]
    print(f"  还原的 16B 源: {bytes(src).hex(' ')}")
    p = zh.find(bytes(src))
    print(f"  ROM 命中: {'0x%08X' % (BASE + p) if p >= 0 else '-'}")
    pj = ja.find(bytes(src))
    print(f"  原版命中: {'0x%08X' % (BASE + pj) if pj >= 0 else '-'}")

# 直接看缓冲的像素对分布
from collections import Counter
print("\n=== 缓冲全部 16 个像素对 ===")
c = Counter(buf[k:k + 2] for k in range(0, 32, 2))
for p, n in c.most_common():
    inpal = p in pal2idx
    print(f"  {p.hex()} x{n}  {'在PAL' if inpal else '✘'}")
