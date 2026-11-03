#!/usr/bin/env python3
"""查证：「！」在 AXVJ 的原版 PCS 里到底是什么字形。

背景：战场对话 `あ！ やせいの` 原版显示的是**半角**「!」，而 charmap 里
      写的是 `3C=！`（全角）。译文用了全角「！」，实测渲染成畸形叠字。

做法：直接从原版 ROM 的字体 tile 里把 0x3C 这个单字节字符的字模挖出来，
      打印成 ASCII 点阵，看它到底是半角还是全角，宽几像素。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

# JP PCS 单字节字符用的字体表（日版原版字库）。
# 地址来自项目既有的字体分析：FontFuncTable 在前，单字节字模表是
# 一组 8 宽的 4bpp tile。这里用「文本已知内容 + 已知排版」反推太绕，
# 改为直接扫 ROM 里连续 4bpp tile 的区段，找与 '!' 形状匹配的。
# 更可靠：用 charmap 的 3C 码位在原版字库里的索引 = 0x3C。


def tile_4bpp(data: bytes, off: int) -> list[list[int]]:
    """解一个 8x8 4bpp tile（32 字节）成 8x8 的 0..15 值。"""
    px = [[0] * 8 for _ in range(8)]
    for y in range(8):
        for x in range(4):
            b = data[off + y * 4 + x]
            px[y][x * 2] = b & 0xF
            px[y][x * 2 + 1] = b >> 4
    return px


def show(px, on="##", off=".."):
    for row in px:
        print("  " + "".join(on if v else off for v in row))


def main() -> int:
    rom = ROM.read_bytes()
    print(f"ROM {ROM.name} {len(rom)}B")

    # 原版字库区：项目里已确认单字节字模在 0x081B0000 附近起步。
    # 先打印 0x3C*32 附近几个 tile 看看形状。
    for base in (0x081B0000, 0x081B2000, 0x081B4000):
        off = base - 0x08000000 + 0x3C * 32
        if off + 32 > len(rom):
            continue
        px = tile_4bpp(rom, off)
        ink = sum(1 for r in px for v in r if v)
        print(f"\nbase=0x{base:08X} +0x3C tile ink={ink}")
        show(px)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
