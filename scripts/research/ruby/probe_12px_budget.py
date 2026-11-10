#!/usr/bin/env python3
"""验算：12px 字宽在 ruby 32-tile 宽 tilemap 下每行能放几个字，是否会溢出。

背景（docs/POKEMON_RUBY_AXVJ00.md §2.3 / §5）：
  落址 index = tileY*32 + tileX       tilemap 宽 32 tile = 256 px
  一个汉字占「竖直相邻两格」：upper @ idx，lower @ idx+32
  即 1 个汉字 = 1 个 tile 列 × 2 tile 行

  字模 16×16，但 CHS_GLYPH_ADVANCE_PX = 12 → 每字实际占 12px 宽
  这就产生「tile 列占用」与「像素步进」不整除的问题。

本脚本纯算术验算，回答：
  1. 12px 步进下，N 个汉字需要多少 tile 列
  2. 相对原版 8px 日文，同一窗口能少放几个字
  3. 窗口宽度约束（GBA 240px 屏，32 tile）

用法：
    python scripts/research/ruby/probe_12px_budget.py
"""
from __future__ import annotations

import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TILEMAP_COLS = 32        # tile 列数（硬编码）
SCREEN_PX = 240          # GBA 屏宽
TILE_PX = 8

ADVANCES = [
    ("日版 8px", 8),
    ("现行 12px", 12),
    ("火红 12px(Small)", 12),
    ("候选 11px", 11),
    ("候选 13px", 13),
]


def main() -> int:
    print(f"tilemap {TILEMAP_COLS} 列 = {TILEMAP_COLS * TILE_PX} px（屏 {SCREEN_PX} px）\n")

    print("=== 每行可放字数（受屏宽 240px 约束）===")
    for name, adv in ADVANCES:
        n = SCREEN_PX // adv
        print(f"  {name:<18} {SCREEN_PX}/{adv} = {n} 字"
              f"   余 {SCREEN_PX - n * adv} px")

    print("\n=== 每行可放字数（受 32 tile 列约束）===")
    for name, adv in ADVANCES:
        # 每个字占 ceil(adv/8) 个 tile 列？实际是 tilemap 条目按像素步进换算
        cols = (SCREEN_PX + adv - 1) // adv
        tiles_used = (cols * adv + TILE_PX - 1) // TILE_PX
        print(f"  {name:<18} {cols} 字  占 {tiles_used}/{TILEMAP_COLS} tile 列")

    print("\n=== 汉字宽度 16px，步进 12px → 相邻字重叠 4px ===")
    for name, adv in ADVANCES:
        if adv < 16:
            print(f"  {name:<18} 字模 16px，步进 {adv}px，重叠 {16 - adv}px")
        else:
            print(f"  {name:<18} 字模 16px，步进 {adv}px，间隙 {adv - 16}px")

    print("\n=== charBase 占用估算 ===")
    for name, adv in ADVANCES:
        cols_per_line = SCREEN_PX // adv
        # 每字 2 个 tile（upper+lower），1 屏约 2 行共 4 tile 行
        lines = 2
        tiles = cols_per_line * lines * 2
        print(f"  {name:<18} {cols_per_line} 字/行 × {lines} 行 × 2 tile = {tiles} tile"
              f"（{tiles * 32} B）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
