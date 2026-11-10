"""确认 VRAM 小字 tile 与 IWRAM 0x03003DE0 的关系，并检查采样时机。

═══ 247 的困境 ═══
0x03003DE0 的内容能反解出「全部 16 个像素对都在 PAL 里」，
但还原出的 16B 源在所有 IDX 候选组合下都不在 ROM 里。

可能原因：
 A. 0x03003DE0 此刻存的是「下一个待画的字」，而不是 VRAM 里已有的小字
 B. 小字的源不在 ROM，是运行时合成的
 C. 采样时刻 0x03003DE0 已被覆盖/半写

本脚本：
 ① 直接对比 VRAM 小字 tile 与 0x03003DE0 的 32B——相同就说明是同一个字
 ② 若不同，说明 0x03003DE0 是别的字（下一帧要画的）
 ③ 检查 EWRAM 里小字副本（0x02001F08）与 0x03003DE0 的关系
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
P = ROOT / "work" / "_probe" / "party232"
vr = (P / "s05_party_vram.bin").read_bytes()
iw = (P / "s05_party_iwram.bin").read_bytes()
ew = (P / "s05_party_ewram.bin").read_bytes()

IWR_BUF = iw[0x03003DE0 - 0x03000000:0x03003DE0 - 0x03000000 + 128]

print("=== IWRAM 0x03003DE0 的 128B（4 段）===")
for k in range(4):
    seg = IWR_BUF[k * 32:(k + 1) * 32]
    print(f"  段{k}: {seg.hex(' ')}")

print("\n=== VRAM 小字 tile 的 32B ===")
for t in (137, 213, 267, 321, 375):
    seg = vr[t * 32:t * 32 + 32]
    inp = IWR_BUF.find(seg)
    print(f"  tile {t}: {seg.hex(' ')}")
    print(f"          在 IWRAM 缓冲内: {('段' + str(inp // 32)) if inp >= 0 else '否'}")

print("\n=== EWRAM 小字副本与 IWRAM 缓冲的关系 ===")
for t in (137, 213, 267, 321, 375):
    seg = vr[t * 32:t * 32 + 32]
    pe = ew.find(seg)
    pi = iw.find(seg)
    print(f"  tile {t}: EWRAM={'0x%08X' % (0x02000000+pe) if pe>=0 else '-'}  "
          f"IWRAM={'0x%08X' % (0x03000000+pi) if pi>=0 else '-'}")

# 看 IWRAM 里 0x03003DE0 附近，除了这 128B 还有没有别的小字
print("\n=== IWRAM 0x03003D00..0x03003F00 全文 ===")
o = 0x03003D00 - 0x03000000
for i in range(0, 0x200, 32):
    seg = iw[o + i:o + i + 32]
    mark = ""
    if 0x03003DE0 - 0x03000000 <= o + i < 0x03003DE0 - 0x03000000 + 128:
        mark = "  ← 解码缓冲"
    print(f"  0x{0x03003D00 + i:08X}  {seg.hex(' ')}{mark}")

# 关键：小字在 VRAM 的 tile 序号是 137，而 137*32 = 0x1120
# 检查 VRAM 0x1120 附近的 tile 是否连续排布（可能是一片小字区）
print("\n=== VRAM tile 130..150 的内容概览 ===")
for t in range(130, 151):
    seg = vr[t * 32:t * 32 + 32]
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = seg[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    ink = int(((m == 11) | (m == 12)).sum())
    vals = sorted(set(int(x) for x in m.flatten()))
    print(f"  tile {t}: 墨={ink:>3} 值域={vals[:8]}  {seg[:8].hex()}")
