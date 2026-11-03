#!/usr/bin/env python3
"""调研⑨ 在**确认为文本**的区间内，统计 F7 的真实码位空间。

═══════════════════════════════════════════════════════════════════════════
【为什么这轮结论可信】
═══════════════════════════════════════════════════════════════════════════
前几轮统计全 ROM 的 F7 → 混入压缩/图形数据，得到 8000+ 码位（不可信）。

本轮只在**已确认为文本**的区间统计：
    ROM 0x086D0000 起，360,448 字节
    实测 F7 占比 27.3%（98,578 个），样本形如
        F7 00 35 F7 00 36 F0 F7 00 97 AB ...
    ⇒ 纯文本，没有任何位图特征

═══════════════════════════════════════════════════════════════════════════
【要回答】
═══════════════════════════════════════════════════════════════════════════
1. 这个文本区里到底用了多少个不同的 (hi,lo) 码位？
2. hi 的取值范围是什么？（决定「能不能压成 2 字节」）
3. 按出现频次排序，覆盖多少比例需要多少码位（看长尾）

用法：python scripts/research/firered/09_text_codespace.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
START = 0x6D0000
SIZE = 0x58000


def main() -> int:
    rom = FR_ZH.read_bytes()
    seg = rom[START:START + SIZE]
    print(f"文本区 ROM 0x{0x08000000+START:08X}  {len(seg):,} B\n")

    pairs = Counter()
    i = seg.find(b"\xf7")
    n = 0
    while i >= 0 and i + 2 < len(seg):
        pairs[(seg[i + 1], seg[i + 2])] += 1
        n += 1
        i = seg.find(b"\xf7", i + 1)

    print(f"F7 编码总数 {n:,}")
    print(f"**不同码位：{len(pairs):,}**")

    his = sorted({h for h, l in pairs})
    los = sorted({l for h, l in pairs})
    print(f"\nhi 用到 {len(his)} 种：0x{min(his):02X} – 0x{max(his):02X}")
    print(f"lo 用到 {len(los)} 种：0x{min(los):02X} – 0x{max(los):02X}")

    by_hi = Counter()
    for (h, l), c in pairs.items():
        by_hi[h] += 1
    print("\n各 hi 页的使用（前 16）：")
    for h in sorted(by_hi)[:16]:
        print(f"  hi=0x{h:02X}  {by_hi[h]:>3}/256 个 lo 值，"
              f"共 {sum(c for (hh,_),c in pairs.items() if hh==h):>7,} 次")

    # 频次覆盖：按出现次数降序累加
    freq = sorted(pairs.values(), reverse=True)
    tot = sum(freq)
    print(f"\n=== 频次覆盖率（决定字库能砍到多小）===")
    for k in (500, 1000, 2000, 3000, 4000, 6000):
        if k > len(freq):
            break
        covered = sum(freq[:k])
        print(f"  前 {k:>5} 个高频字覆盖 {covered/tot*100:>5.1f}% 的出现次数")

    print(f"\n=== 结论 ===")
    nc = len(pairs)
    print(f"  真实码位 {nc:,}")
    if nc <= 4096:
        print(f"  ⇒ **12 位足够 ⇒ 可以压成 2 字节**（4 位页 + 8 位偏移）")
        print(f"     或者更激进：若只保留前 4096 高频字，覆盖 "
              f"{sum(freq[:4096])/tot*100:.1f}% 的出现次数")
    else:
        print(f"  ⇒ 超过 12 位（4096），2 字节放不下全部")
        print(f"     但前 4096 高频字能覆盖 {sum(freq[:min(4096,len(freq))])/tot*100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
