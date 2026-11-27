#!/usr/bin/env python3
"""并排渲染「本项目 small 字库」与「美版汉化版 small 字库」同字符对比图。

═══════════════════════════════════════════════════════════════════
为什么有这个脚本
═══════════════════════════════════════════════════════════════════
两套字库来源完全不同，肉眼在游戏截图里很难分清差在哪：

  本项目 small.bdf      : nibble 有 1..12 多级灰度（抗锯齿），宽 9px
  汉化版 small 字库     : 只有 0 / 14(阴影) / 15(主墨) 三色，宽 8px

所以直接把两边的 nibble 网格按同一放大倍数画出来并排看，比截图可靠。

═══════════════════════════════════════════════════════════════════
数据来源
═══════════════════════════════════════════════════════════════════
汉化版：work/_us_cn.gba，字库基址 0x090DB0A0，128B/字，
        idx 由 GitHub Wokann/Pokemon_GBA_Font_Patch 的 TBL 码表反查。
本项目：configs/POKEMON_RUBY_AXVJ00/fonts/small.bdf

用法
====
    python scripts/font/export/compare_fonts.py --chars 火焰鸡宝可梦
    python scripts/font/export/compare_fonts.py --out work/_cmp.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/font"))
sys.path.insert(0, str(ROOT / "scripts/font/export"))

from build_chinese_font import parse_bdf            # noqa: E402
from map_us_cn_to_unicode import load_tbl           # noqa: E402

US_CN_ROM = ROOT / "work/_us_cn.gba"
FONT_BASE = 0x090DB0A0
BYTES_PER_GLYPH = 128

OURS_BDF = ROOT / "configs/POKEMON_RUBY_AXVJ00/fonts/small.bdf"

SCALE = 6


def us_cn_nibbles(rom: bytes, idx: int) -> list[list[int]]:
    """汉化版 idx 号字形 → 8x16 nibble 网格（只取 tile0+tile1）。"""
    a = FONT_BASE - 0x08000000 + idx * BYTES_PER_GLYPH
    out: list[list[int]] = []
    for tile in range(2):
        for y in range(8):
            out.append([
                ((rom[a + tile * 32 + y * 4 + x // 2] & 0x0F) if x % 2 == 0
                 else (rom[a + tile * 32 + y * 4 + x // 2] >> 4))
                for x in range(8)
            ])
    return out


def ours_nibbles(bdf: dict, ch: str) -> list[list[int]] | None:
    """本项目 BDF 字形 → nibble 网格（值为 0 或 15）。

    ★ 本项目 small.bdf 是 **1bpp**（BBX 16 16，每行 2 字节 = 16 个 bit），
      每个 bit 就是一个像素。**绝不能当 nibble 拆** —— 那样 16px 会被当成
      32px、每位被解释成 4bit 值，实测只剩 3 列有效，画出来就是一根竖条。
    """
    cp = ord(ch)
    if cp not in bdf:
        return None
    rows = bdf[cp][0]
    grid: list[list[int]] = []
    for row in rows[:16]:
        r: list[int] = []
        for byte in row:
            for b in range(7, -1, -1):
                r.append(15 if (byte >> b) & 1 else 0)
        grid.append(r)
    while len(grid) < 16:
        grid.append([0] * 16)
    for r in grid:
        while len(r) < 16:
            r.append(0)

    # 裁右侧空白列
    last = -1
    for r in grid:
        for x, v in enumerate(r):
            if v:
                last = max(last, x)
    if last < 0:
        return [[0] * 8 for _ in range(16)]
    w = min(last + 1, 16)
    return [r[:w] for r in grid]


def main() -> int:
    ap = argparse.ArgumentParser(description="两套 small 字库并排对比")
    ap.add_argument("--chars", default="火焰鸡宝可梦红蓝绿战斗等级")
    ap.add_argument("--out", type=Path, default=ROOT / "work/_font_compare.png")
    ap.add_argument("--scale", type=int, default=SCALE)
    ap.add_argument("--cols", type=int, default=4)
    args = ap.parse_args()

    rom = US_CN_ROM.read_bytes()
    tbl = load_tbl()
    char2idx = {ch: idx for idx, ch in tbl.items() if len(ch) == 1}
    ours, *_ = parse_bdf(OURS_BDF)

    chars = [c for c in args.chars if c.strip()]
    S = args.scale
    cellw = 16 * S + 40
    cellh = 16 * S + 30
    cols = args.cols
    rows = (len(chars) + cols - 1) // cols

    img = Image.new("RGB", (cellw * cols + 16, cellh * rows + 16), (248, 248, 248))
    d = ImageDraw.Draw(img)
    try:
        fnt = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 13)
    except OSError:
        fnt = ImageFont.load_default()

    def draw(nib: list[list[int]], ox: int, oy: int, base: tuple[int, int, int]) -> None:
        for y, row in enumerate(nib):
            for x, v in enumerate(row):
                if v == 0:
                    continue
                if v in (14, 15):
                    c = base
                else:
                    # 本项目字库的灰度：按明度向白插值
                    t = 1.0 - v / 15.0
                    c = tuple(int(b2 * (1 - t) + 255 * t) for b2 in base)
                d.rectangle([ox + x * S, oy + y * S,
                             ox + x * S + S - 1, oy + y * S + S - 1], fill=c)

    def width_of(nib: list[list[int]]) -> int:
        last = -1
        for r in nib:
            for x, v in enumerate(r):
                if v:
                    last = max(last, x)
        return last + 1

    miss = []
    for i, ch in enumerate(chars):
        cx = (i % cols) * cellw + 8
        cy = (i // cols) * cellh + 8
        o = ours_nibbles(ours, ch)
        idx = char2idx.get(ch)
        t = us_cn_nibbles(rom, idx) if idx is not None else None

        ow = width_of(o) if o else 0
        tw = width_of(t) if t else 0
        d.text((cx, cy),
               f"{ch} 本项目{ow}px / 汉化版{tw}px",
               fill=(60, 60, 60), font=fnt)
        y0 = cy + 17

        if o:
            draw(o, cx, y0, (40, 90, 200))
        else:
            miss.append(f"本项目缺 {ch}")
        if t:
            draw(t, cx + ow * S + 26, y0, (200, 50, 50))
        else:
            miss.append(f"汉化版缺 {ch}")

        d.text((cx, y0 + 16 * S + 2), "本项目", fill=(40, 90, 200), font=fnt)
        d.text((cx + ow * S + 26, y0 + 16 * S + 2), "汉化版", fill=(200, 50, 50), font=fnt)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    img.save(args.out)
    print(f"写入 {args.out}")
    print(f"  左(蓝)=本项目 small.bdf 9px 带灰度  右(红)=汉化版 8px 三色")
    if miss:
        print("  缺失:", "; ".join(miss))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())