#!/usr/bin/env python3
"""澄清：扩容空间不是约束，真正的约束是「代码怎么读」。

核心事实：
  1. ROM 早就扩容（expands_rom: true，当前产物 30.65 MB）
  2. 表体积需求仅 ~70 KB，空间完全不是问题
  3. 所以「stride 放大」的代价不是空间，而是【改机器码】

真正的问题：
  放大 stride 后，代码里 index×stride 的乘法必须同步改。
  这才是要评估的成本。

空间账（实测）：
  当前产物      32,138,048 B (30.65 MB)
  32MB 上限     33,554,432 B → 剩 1.35 MB
  64MB 上限     67,108,864 B → 剩 33.35 MB

  7 张表全换新   71,532 B (70 KB)

⇒ 即使只扩到 32MB，也塞得下 70KB 的几十倍。
   若删掉 PhraseTable（F980 废掉后）和 SlotTable（SLT2 废掉后），
   能额外释放数 MB。

用法：
    python scripts/research/ruby/a2_space_budget.py
"""
from __future__ import annotations

import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 当前布局（从 game_addrs.asm）
LAYOUT = [
    ("原版 ROM",            0x00000000, 0x00800000, "8 MB 原版"),
    ("game.bin",            0x00800000, 0x00810000, "≤64 KB hook 代码"),
    ("PhraseOffsets",       0x00810000, 0x00820000, "F980 废掉后释放"),
    ("PhraseTable",         0x00820000, 0x00900000, "F980 废掉后释放"),
    ("FontChsNormal",       0x00900000, 0x00910000, "1 MB 中文字库"),
    ("FontChsSmall",        0x00910000, 0x009E0000, "小字库"),
    ("PokeRSFontChsSym",    0x009E0000, 0x009F0000, "符号库"),
    ("FontChsMiddle",       0x009F0000, 0x00A00000, "中字库"),
    ("SlotTable",           0x00EA0000, 0x00EB0000, "SLT2 废掉后释放"),
]

# 表扩容需求
TABLE_COST = [
    ("招式名",         354, 8,  32),
    ("特性名",         77,  8,  32),
    ("属性名",         18,  5,  20),
    ("道具名",         348, 40, 80),
    ("图鉴分类名",     386, 28, 56),
    ("秘密基地装饰名", 120, 28, 56),
    ("树果名",         43,  28, 28),
]


def main() -> int:
    print("=== 当前扩展区布局 ===")
    print(f"  {'区域':<20} {'起始':>10} {'结束':>10} {'说明'}")
    for name, lo, hi, note in LAYOUT:
        print(f"  {name:<20} 0x{lo:08X} 0x{hi:08X}  {note}")

    cur = 32_138_048
    print()
    print(f"=== 空间余量 ===")
    print(f"  当前产物 {cur:,} B = {cur / 1024 / 1024:.2f} MB")
    for cap_mb in (16, 32, 64):
        cap = cap_mb * 1024 * 1024
        left = cap - cur
        mark = "✅" if left > 0 else "❌ 已超"
        print(f"  {cap_mb:>2} MB 上限 → 剩 {left / 1024 / 1024:>7.2f} MB  {mark}")

    print()
    print("=== 7 张表全换新的空间需求 ===")
    total = 0
    print(f"  {'表':<16} {'项数':>5} {'旧stride':>9} {'新stride':>9} {'新体积':>10}")
    for name, n, old_s, new_s in TABLE_COST:
        size = n * new_s
        total += size
        print(f"  {name:<16} {n:>5} {old_s:>9} {new_s:>9} {size:>10,} B")
    print(f"  {'合计':<16} {'':>5} {'':>9} {'':>9} {total:>10,} B "
          f"({total / 1024:.1f} KB)")

    print()
    print("=== 结论 ===")
    print(f"  表扩容只需 {total:,} B（{total/1024:.1f} KB）")
    print(f"  32 MB 上限剩余 1.35 MB → 够放 {1.35*1024*1024/total:.0f} 倍")
    print()
    print("  ⇒ 空间不是任何方案的约束条件。")
    print("  ⇒ 真正的约束是「放大 stride 必须同步改机器码」。")

    print()
    print("=== 删掉 F980/SLT2 后可释放 ===")
    for name, lo, hi, note in LAYOUT:
        if "释放" in note:
            print(f"  {name:<20} 0x{hi - lo:>10,} B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
