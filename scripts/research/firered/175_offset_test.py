#!/usr/bin/env python3
"""调研(175) 测试固定偏移假设：VRAM nibble 10/11/12 可能是 ROM 的 1/2/3（差 -9）。

═══════════════════════════════════════════════════════════════════════════
【思路】
═══════════════════════════════════════════════════════════════════════════
VRAM tile 1:  aa aa aa aa aa aa aa aa aa aa aa aa aa aa cb cb
  0xAA = nibble(10,10)   0xCB = nibble(12,11)

若 ROM 里存的是「1/2/3」三档（比 VRAM 小 9）：
  10 → 1   11 → 2   12 → 3

  tile 1 → 11 11 11 11 11 11 11 11 11 11 11 11 11 11 32 32
  tile 2 → 11 11 ...

这解释了我之前所有搜索失败的原因：
  · 试过 "012" 归一化（10→0,11→1,12→2）✗
  · **没试过 10→1,11→2,12→3**（差 9）

【本脚本穷举所有偏移】
 对 offset ∈ {-9, +9, 0, -10, -8, -6, ...} 全试一遍，
 以及「只保留墨迹的 1bpp 掩码」，去两个 ROM 搜。

用法：python scripts/research/firered/175_offset_test.py
"""
from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def shift_nib(blob: bytes, fn) -> bytes:
    out = bytearray()
    for b in blob:
        hi, lo = b >> 4, b & 0x0F
        out.append(((fn(hi) & 0xF) << 4) | (fn(lo) & 0xF))
    return bytes(out)


def main() -> int:
    vr = (SNAP / "vram.bin").read_bytes()
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()

    # 取文字 tile 1..7（tilemap 行1 的 pal=15 项）
    tiles = {i: vr[i * 32:(i + 1) * 32] for i in range(1, 8)}
    # 用最长的连续段（tile 1..7 = 224 字节）作为主搜索模式
    joined = b"".join(tiles[i] for i in range(1, 8))
    print(f"搜索模式：tiles 1..7 连续 = {len(joined)} 字节")
    print(f"  前 48: {joined[:48].hex(' ')}")

    # ── ① 穷举偏移 ────────────────────────────────────
    print("\n" + "=" * 78)
    print("① 穷举 nibble 偏移（10→1, 11→2, 12→3 这类）")
    print("=" * 78)

    def make_shift(d: int):
        return lambda v: v + d if v >= 10 else (0 if v == 0 else v)

    results = []
    for d in range(-12, 13):
        fn = make_shift(d)
        pat = shift_nib(joined, fn)
        if len(set(pat)) <= 2:
            continue
        for rname, rom in (("汉化", zh), ("原版", ja)):
            i = rom.find(pat)
            if i >= 0:
                n = 0
                j = i
                while j >= 0 and n < 50:
                    n += 1
                    j = rom.find(pat, j + 1)
                results.append((d, rname, i, n))
    if results:
        for d, rname, off, n in results:
            print(f"  ★ 偏移 {d:+d} 在{rname}命中 {n} 处，首个 0x{BASE+off:08X}")
    else:
        print("  所有偏移都 0 命中")

    # ── ② 只搜墨迹掩码（1bpp，与调色板无关）───────────
    print("\n" + "=" * 78)
    print("② 墨迹掩码（1bpp）：nibble 12→1，其余→0")
    print("=" * 78)

    def ink_mask(blob: bytes, val: int = 12) -> bytes:
        out = bytearray()
        # 每 tile 32B → 8 行 × 4B；每行 8 px → 1B
        for y in range(0, 8):
            row = 0
            for x in range(8):
                idx = y * 4 + x // 2
                if idx >= len(blob):
                    break
                b = blob[idx]
                p = (b & 0xF) if x % 2 == 0 else (b >> 4)
                row = (row << 1) | (1 if p == val else 0)
            out.append(row)
        return bytes(out)

    # 对每个 tile 单独做 8 字节掩码
    for i in range(1, 8):
        pat = ink_mask(tiles[i], 12)
        if len(set(pat)) <= 1:
            continue
        for rname, rom in (("汉化", zh), ("原版", ja)):
            hits = []
            j = rom.find(pat)
            while j >= 0 and len(hits) < 30:
                hits.append(j)
                j = rom.find(pat, j + 1)
            if hits:
                z = Counter(h // 0x10000 for h in hits)
                top = ", ".join(f"0x{BASE+k*0x10000:08X}:{v}"
                                for k, v in z.most_common(3))
                print(f"  tile{i} [{rname}] 命中 {len(hits)}  分布 {top}")

    # ── ③ 11+12 都算墨 ────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 墨迹掩码：11 或 12 → 1")
    print("=" * 78)
    for i in range(1, 8):
        pat = ink_mask(tiles[i], 11)  # 先算 11 的
        # 合并 11 和 12
        p11 = ink_mask(tiles[i], 11)
        p12 = ink_mask(tiles[i], 12)
        pat = bytes(a | b for a, b in zip(p11, p12))
        if len(set(pat)) <= 1:
            continue
        cnt = 0
        for rname, rom in (("汉化", zh), ("原版", ja)):
            j = rom.find(pat)
            while j >= 0 and cnt < 40:
                cnt += 1
                j = rom.find(pat, j + 1)
        if cnt:
            print(f"  tile{i} 命中 {cnt}")

    # ── ④ 直接汇报：文字 tile 的原始字节是否在 ROM 任何位置 ─
    print("\n" + "=" * 78)
    print("④ 逐个文字 tile 完整 32 字节搜索（两版）")
    print("=" * 78)
    for i in range(1, 12):
        b = tiles.get(i) or vr[i * 32:(i + 1) * 32]
        if len(set(b)) <= 2:
            print(f"  tile{i:>2}: 内容过简，跳过")
            continue
        hz = zh.find(b)
        hj = ja.find(b)
        print(f"  tile{i:>2}: 汉化 {'命中 0x%08X' % (BASE+hz) if hz >= 0 else '无'}"
              f"  原版 {'命中 0x%08X' % (BASE+hj) if hj >= 0 else '无'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
