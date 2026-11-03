#!/usr/bin/env python3
"""调研② 确认火红的 0xF7 是 2 字节还是 3 字节编码，并解出字符集规模。

═══════════════════════════════════════════════════════════════════════════
【上一轮的结论】
═══════════════════════════════════════════════════════════════════════════
火红汉化版相对原版，只有 0xF7 显著增多（49,212 → 171,834，+122,622），
0xF9 几乎没动（20,505 → 21,328）。

⇒ 火红**只用了 F7 一种中文编码前缀**，不像我们红宝石工程同时用 F9 00/F9 80。

═══════════════════════════════════════════════════════════════════════════
【本轮要回答】
═══════════════════════════════════════════════════════════════════════════
1. F7 后面跟 **1 个字节还是 2 个字节**？（决定是 2 字节还是 3 字节编码）
2. 可表示多少个汉字？（决定字库上限）
3. 有没有子分类（比如 F7 80-FF 是一类，F7 00-7F 是另一类）？

方法：找 ROM 里连续的 F7 序列，看它们的**后继字节分布**：
  · 如果 F7 后面总是「单字节在某个范围」，那是 2 字节编码
  · 如果 F7 后面总是「两个字节都可变」，那是 3 字节编码
再统计 F7 后继字节的唯一值个数 ≈ 可编码字符数。

用法：python scripts/research/firered/02_f7_structure.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()

    # 找所有 F7 位置
    pos = []
    i = zh.find(b"\xf7")
    while i >= 0:
        pos.append(i)
        i = zh.find(b"\xf7", i + 1)
    print(f"汉化版 F7 出现 {len(pos):,} 次")

    # 1) 后继字节分布（第 1 个）
    nxt1 = Counter()
    for p in pos:
        if p + 1 < len(zh):
            nxt1[zh[p + 1]] += 1
    print(f"\nF7 后继字节（第 1 字节）的唯一值: {len(nxt1)} 种")
    top = nxt1.most_common(12)
    print("  最常见的 12 个:")
    for b, n in top:
        print(f"    0x{b:02X}  {n:>8,} 次")

    # 2) 第 2 字节分布（若为 3 字节编码，第 2 字节也该多样）
    nxt2 = Counter()
    for p in pos:
        if p + 2 < len(zh):
            nxt2[zh[p + 2]] += 1
    print(f"\nF7 后第 2 字节的唯一值: {len(nxt2)} 种")
    print("  最常见的 8 个:")
    for b, n in nxt2.most_common(8):
        print(f"    0x{b:02X}  {n:>8,} 次")

    # 3) 关键判据：F7 后面**紧跟另一个 F7** 的比例
    #    2 字节编码时，连续汉字会出现 F7 xx F7 xx（间隔 2）
    #    3 字节编码时，间隔 3
    gaps = Counter()
    for a, b in zip(pos, pos[1:]):
        d = b - a
        if d <= 8:
            gaps[d] += 1
    print("\n相邻 F7 的间距分布（前 6）:")
    for d, n in gaps.most_common(6):
        print(f"    间距 {d}: {n:>8,} 次")

    # 4) 抽样看具体字节
    print("\n抽样 8 处（F7 前后各 6 字节）:")
    step = max(1, len(pos) // 8)
    for k in range(0, min(len(pos), step * 8), step):
        p = pos[k]
        lo, hi = max(0, p - 6), min(len(zh), p + 7)
        seg = zh[lo:hi]
        # 标出 F7 位置
        rel = p - lo
        hexs = " ".join(f"{b:02X}" for b in seg)
        print(f"  @0x{p:08X}  {hexs}   (F7 在偏移 {rel})")

    # 5) 对比原版同位置
    print("\n原版同位置对照（前 3 处）:")
    for k in range(0, min(len(pos), 3)):
        p = pos[k]
        lo, hi = max(0, p - 6), min(len(ja), p + 7)
        seg = ja[lo:hi]
        print(f"  @0x{p:08X}  " + " ".join(f"{b:02X}" for b in seg))

    print("\n=== 判读 ===")
    print(f"  F7 后继字节种类 {len(nxt1)} 种，第 2 字节种类 {len(nxt2)} 种")
    print("  若后继种类 ≈ 100-200 且第 2 字节种类很少 ⇒ **2 字节编码**")
    print("  若两者都上百 ⇒ 3 字节编码")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
