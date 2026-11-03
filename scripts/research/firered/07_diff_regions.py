#!/usr/bin/env python3
"""调研⑦ 用「汉化版 vs 原版」的差异区定位改动，而不是猜结构。

═══════════════════════════════════════════════════════════════════════════
【为什么这是最可靠的路】
═══════════════════════════════════════════════════════════════════════════
前几轮都是在**猜结构**（猜码位表、猜字模步长），都失败了。
但有个铁的事实：**汉化版 = 原版 + 改动**。

所以直接算「两个 ROM 哪里不同」，差异区必然包含：
  · 新增的中文字模
  · 改写的文本（F7 编码）
  · 可能改动的码位映射表

差异区之外的部分就是原版的日文字库和代码，**不用管**。

方法：按 4KB 块比对，找出差异块的分布，再对差异区内做细分：
  · 差异密集且重复 → 字模区
  · 差异稀疏且呈字符串状 → 文本区

用法：python scripts/research/firered/07_diff_regions.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BLK = 0x1000


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja)) // BLK
    print(f"比对 {n} 个 4KB 块（共 {n*BLK:,} B）\n")

    diff_blocks = []
    for i in range(n):
        a = ja[i * BLK:(i + 1) * BLK]
        b = zh[i * BLK:(i + 1) * BLK]
        if a != b:
            d = sum(1 for k in range(BLK) if a[k] != b[k])
            diff_blocks.append((i, d))

    print(f"有差异的块：{len(diff_blocks)} / {n} "
          f"（{len(diff_blocks)/n*100:.1f}%）")
    print(f"差异总字节：{sum(d for _, d in diff_blocks):,}")

    # 把差异块聚合成连续区间
    runs = []
    if diff_blocks:
        s = p = diff_blocks[0][0]
        tot = diff_blocks[0][1]
        for idx, d in diff_blocks[1:]:
            if idx == p + 1:
                p, tot = idx, tot + d
            else:
                runs.append((s, p, tot))
                s = p = idx
                tot = d
        runs.append((s, p, tot))
    runs.sort(key=lambda r: -r[2])

    print(f"\n=== 差异最大的 15 个连续区间 ===")
    print(f"{'ROM 地址':>12} {'块数':>6} {'差异字节':>10} {'密度'}")
    for s, p, tot in runs[:15]:
        nb = p - s + 1
        dens = tot / (nb * BLK)
        print(f"0x{0x08000000+s*BLK:08X} {nb:>6} {tot:>10,} {dens*100:>5.1f}%")

    print("\n=== 判读要点 ===")
    print("  · 密度接近 100% 且区间很大 → 整块被替换（字模区/文本区）")
    print("  · 密度低（<20%）→ 零散改动（指针修正、少量文本）")
    print("  · 汉化通常把新数据追加到 ROM 末尾附近，原版数据基本不动")
    print("\n下一步：对差异密度最高的区间，抽样打印字节，")
    print("      看是位图（规律 4bpp 数据）还是文本（F7 序列）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
