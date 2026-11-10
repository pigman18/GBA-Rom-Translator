#!/usr/bin/env python3
"""调研(98) 定案：字库在 ROM 0x08B5xxxx 一带，1bpp 格式。

═══════════════════════════════════════════════════════════════════════════
【(97) 的关键发现】
═══════════════════════════════════════════════════════════════════════════
  0x08B50000: ff ff 6f fd | a6 56 f9 a6 | 6e 55 a6 a6 | b9 d5 6e d6
  0x08B60000: ff ff f6 ff | f6 ff f6 ff | f6 f6 f5 f6 | f6 f6 f6 f6

特征：
  · 以 `ff ff` 开头（2 字节空白边距）
  · 后续字节是 `6f / fd / a6 / 56 / d5 / 9a / aa / e6` 这类
    高/低 nibble 都非 0 非 F 的模式 ⇒ **1bpp 位图的典型笔迹**
  · 熵 2.0~3.0（远低于压缩数据的 7+）⇒ 不是压缩
  · 原版该区 100% FF ⇒ 汉化完全新增

⇒ 字库 = **1bpp 位图数组**，直接从 ROM 读，运行时展开成 4bpp 上屏。
  这就解释了为什么 VRAM 的字形字节在 ROM 里搜不到
  （4bpp 4 字节/行 vs 1bpp 1.375 字节/行，形式不同）。

【本脚本】
 ① 定出单字的字节尺寸（试 16/18/22/24 字节）
 ② 按最合理的尺寸切，画成 ASCII，看能否读出汉字
 ③ 找出数组起点与总个数
 ④ 导出整张字库图

用法：python scripts/research/firered/98_font_1bpp.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
BASE = 0x08000000


def draw_1bpp(blob: bytes, w: int, h: int, row_bytes: int,
              label: str = "") -> None:
    print(f"\n  {label}  {w}×{h}  row_bytes={row_bytes}  "
          f"共 {len(blob)} 字节")
    for y in range(h):
        row = blob[y * row_bytes:(y + 1) * row_bytes]
        if len(row) < row_bytes:
            break
        bits = int.from_bytes(row, "big")
        total = row_bytes * 8
        line = "".join("#" if (bits >> (total - 1 - x)) & 1 else "."
                       for x in range(min(w, total)))
        print(f"    {line}")


def main() -> int:
    zh = FR_ZH.read_bytes()

    print("=" * 78)
    print("① 0x08B00000 区块里找「非 FF 的起点」")
    print("=" * 78)
    # 先确认哪个偏移开始有真数据
    for base in (0xB00000, 0xB48000, 0xB50000, 0xB60000, 0xB70000,
                 0xB80000, 0xB90000):
        seg = zh[base:base + 0x8000]
        nz = sum(1 for b in seg if b != 0xFF)
        print(f"  0x{BASE+base:08X}: 0x8000 字节里非 FF {nz:>6} "
              f"({nz/0x8000*100:>5.1f}%)")

    print("\n" + "=" * 78)
    print("② 试不同「每字字节数」，看哪个切出来像汉字")
    print("=" * 78)
    off = 0xB50000
    # 11 行 × 2 字节 = 22；12 行 × 2 = 24；11 行 × 3 = 33（太宽）
    for per, w, h, rb in ((22, 11, 11, 2), (24, 12, 12, 2),
                          (18, 11, 11, 2)[:3] + (2,), (16, 16, 8, 2)):
        blob = zh[off:off + per]
        draw_1bpp(blob, w, h, rb, f"每字 {per} 字节")

    print("\n" + "=" * 78)
    print("③ 用 24 字节/字（12 行 × 2 字节）连续画 8 个字")
    print("=" * 78)
    per = 24
    for k in range(8):
        blob = zh[off + k * per: off + (k + 1) * per]
        draw_1bpp(blob, 16, 12, 2, f"第 {k} 字")

    print("\n" + "=" * 78)
    print("④ 也试 0x08B60000 起点")
    print("=" * 78)
    for k in range(4):
        blob = zh[0xB60000 + k * 24: 0xB60000 + (k + 1) * 24]
        draw_1bpp(blob, 16, 12, 2, f"B6 第 {k} 字")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
