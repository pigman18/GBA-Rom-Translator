#!/usr/bin/env python3
"""调研⑬ 火红的 F7 为什么有 42.6% 在「主文本区」之外？那些区是什么？

═══════════════════════════════════════════════════════════════════════════
【上一轮发现】
═══════════════════════════════════════════════════════════════════════════
F7 总数 171,834，分布：
  · 主文本区（0x086D0000 + 0x58000）内：98,578（57.4%）
  · 区外：73,256（42.6%），集中在
      0x08AF0000  5,169    0x08B10000  4,843    0x08B00000  4,798
      0x08730000  2,075    0x08740000  1,958    0x08080000  1,696

这些区外 F7 是关键：
  · 若它们是**第二/第三个新增文本区** → 火红把文本分散追加到多个空洞
  · 若它们在**原版数据区内部**（覆盖了原版数据）→ 火红原地覆盖，
    那就可能改动了数据结构（宝可梦名等）

方法：对这些区做「原版 vs 汉化」的差异密度分析 + 形态判断。

用法：python scripts/research/firered/13_outside_zones.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"


def analyze(zh: bytes, ja: bytes, base: int, size: int, label: str):
    seg_zh = zh[base:base + size]
    seg_ja = ja[base:base + size]
    if len(seg_zh) < size:
        return
    diff = sum(1 for i in range(size) if seg_zh[i] != seg_ja[i])
    c = Counter(seg_zh)
    f7 = c.get(0xF7, 0)
    ff = c.get(0xFF, 0)
    print(f"\n{label}  ROM 0x{0x08000000+base:08X}  {size:,} B")
    print(f"  与原版差异: {diff:,} ({diff/size*100:.1f}%)")
    print(f"  F7: {f7:,} ({f7/size*100:.1f}%)   FF: {ff:,} ({ff/size*100:.1f}%)")
    # 形态判断
    if diff / size > 0.7 and f7 / size > 0.15:
        kind = "几乎整块被替换 + 高 F7 ⇒ **新增文本区**"
    elif diff / size > 0.7:
        kind = "整块被替换但 F7 少 ⇒ **字模/图形区**"
    elif diff / size < 0.3:
        kind = "少量改动 ⇒ 原地补丁"
    else:
        kind = "中等改动"
    print(f"  ⇒ {kind}")
    # 抽样
    print(f"  抽样 +0x000: " + " ".join(f"{b:02X}" for b in seg_zh[:32]))


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()

    zones = [
        (0xAF0000, 0x10000, "区外热点 1"),
        (0xB00000, 0x10000, "区外热点 2"),
        (0xB10000, 0x10000, "区外热点 3"),
        (0x730000, 0x10000, "区外热点 4"),
        (0x080000, 0x10000, "低地址热点"),
        (0x0A0000, 0x10000, "低地址热点 2"),
    ]
    for base, size, label in zones:
        analyze(zh, ja, base, size, label)

    print("\n=== 汇总判读 ===")
    print("  若这些区都是「整块被替换 + 高 F7」⇒ 火红把中文文本分散写在多个位置，")
    print("  而不是集中在 0x086D0000 一个区。")
    print("  这对我们的启示：")
    print("    · 写新区不必集中，可以填原版的空洞/无用数据区")
    print("    · 但必须保证被覆盖的原版数据确实无用（火红显然是这么判断的）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
