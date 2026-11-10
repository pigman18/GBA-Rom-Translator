#!/usr/bin/env python3
"""调研(88) 导出干净的字库图：按汉字格切分，每字单独一格。

═══════════════════════════════════════════════════════════════════════════
【(87) 已确认】
═══════════════════════════════════════════════════════════════════════════
  字库位置：VRAM tile 1..273（0x0020..0x2240）
  排布：24 列 tile = 12 个汉字/行，每汉字 2×2 tile（16×16 像素）
  字形：11×11 有效笔画，抗锯齿 3 色（nibble 10=白 / 11=浅灰 / 12=深灰）
  内容：继续游戏 / 主角 RED / 时间 22:04 / 图鉴 62只 / 徽章 7枚 / 开始新游戏

⚠ (87) 的图里上下两行汉字叠在一起，因为 16px 高的格子间距为 0。

【本脚本改进】
 ① 每个汉字裁成独立 16×16 格子，格子间留 2px 白边
 ② 每行 12 字，分行导出，行间留 4px
 ③ 同时导出「网格版」：每格描边，便于数格
 ④ 附：每格的实际墨量，用来判断哪些格子是空的

用法：python scripts/research/firered/88_clean_atlas.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "glyphs"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def tile_nibbles(vram: bytes, t: int) -> np.ndarray:
    o = t * 32
    if o + 32 > len(vram):
        return np.full((8, 8), 10, dtype=np.uint8)
    blob = vram[o:o + 32]
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            b = blob[y * 4 + x // 2]
            m[y, x] = (b & 0x0F) if x % 2 == 0 else (b >> 4)
    return m


def glyph_cell(vram: bytes, tile_base: int, row: int, col: int) -> np.ndarray:
    """取第 row 行第 col 列的汉字（16×16 nibble）。
    tile 排布：24 列，每汉字占 2×2。
    tile 序号 = (row*2 + dy) * 24 + col*2 + dx
    """
    cell = np.full((16, 16), 10, dtype=np.uint8)
    for dy in range(2):
        for dx in range(2):
            t = tile_base + (row * 2 + dy) * 24 + col * 2 + dx
            cell[dy * 8:(dy + 1) * 8, dx * 8:(dx + 1) * 8] = \
                tile_nibbles(vram, t)
    return cell


def main() -> int:
    from PIL import Image

    vram = (OUT / "g1.vram.bin").read_bytes()

    # 调色板：用于「白底黑字」
    def nib_to_rgb(cell: np.ndarray) -> np.ndarray:
        out = np.full((*cell.shape, 3), 255, dtype=np.uint8)  # 白底
        out[cell == 11] = (150, 150, 150)     # 浅灰（抗锯齿）
        out[cell == 12] = (0, 0, 0)           # 深灰黑（笔画）
        out[cell == 1] = (200, 0, 0)          # 特殊色
        return out

    print("=" * 78)
    print("① 逐格墨量统计（找出非空格）")
    print("=" * 78)
    ROWS, COLS = 6, 12
    base = 1        # tile 1 起
    cells = {}
    for r in range(ROWS):
        for c in range(COLS):
            cell = glyph_cell(vram, base, r, c)
            ink = int(((cell == 11) | (cell == 12) | (cell == 1)).sum())
            cells[(r, c)] = (cell, ink)
        rowink = [cells[(r, c)][1] for c in range(COLS)]
        print(f"  行{r}: 各格墨量 {rowink}")

    # ── ② 导出干净字库（2px 格子间距）────────────────────────────
    print("\n" + "=" * 78)
    print("② 导出干净字库（格间距 2px，行间距 4px）")
    print("=" * 78)
    CW, CH = 16, 16
    GAP = 2
    ROWGAP = 4
    W = COLS * (CW + GAP) + GAP
    H = ROWS * (CH + ROWGAP) + ROWGAP
    canvas = np.full((H, W, 3), 240, dtype=np.uint8)   # 浅灰底，看得清格

    for r in range(ROWS):
        for c in range(COLS):
            cell, ink = cells[(r, c)]
            if ink == 0:
                continue
            y0 = ROWGAP + r * (CH + ROWGAP)
            x0 = GAP + c * (CW + GAP)
            canvas[y0:y0 + CH, x0:x0 + CW] = nib_to_rgb(cell)

    big = np.repeat(np.repeat(canvas, 4, axis=0), 4, axis=1)
    p = OUT / "font_clean_4x.png"
    Image.fromarray(big).save(p)
    print(f"  → {p.name}  ({big.shape[1]}×{big.shape[0]})")
    print(f"    {ROWS} 行 × {COLS} 列 = {ROWS*COLS} 个字位")

    # ── ③ 带网格线的版本（便于数格子）────────────────────────────
    print("\n" + "=" * 78)
    print("③ 带网格线版本")
    print("=" * 78)
    canvas2 = canvas.copy()
    for r in range(ROWS):
        for c in range(COLS):
            y0 = ROWGAP + r * (CH + ROWGAP)
            x0 = GAP + c * (CW + GAP)
            # 画 1px 边框
            canvas2[y0, x0:x0 + CW] = (200, 200, 255)
            canvas2[y0 + CH - 1, x0:x0 + CW] = (200, 200, 255)
            canvas2[y0:y0 + CH, x0] = (200, 200, 255)
            canvas2[y0:y0 + CH, x0 + CW - 1] = (200, 200, 255)
    big2 = np.repeat(np.repeat(canvas2, 4, axis=0), 4, axis=1)
    p2 = OUT / "font_grid_4x.png"
    Image.fromarray(big2).save(p2)
    print(f"  → {p2.name}  ({big2.shape[1]}×{big2.shape[0]})")

    # ── ④ 找出每个字的实际墨迹范围（验证 11×11）──────────────────
    print("\n" + "=" * 78)
    print("④ 逐字量墨迹范围（验证 11×11 字形）")
    print("=" * 78)
    print(f"  {'格':>6} {'墨量':>5} {'x范围':>12} {'y范围':>12} {'宽×高':>8}")
    for r in range(min(3, ROWS)):
        for c in range(COLS):
            cell, ink = cells[(r, c)]
            if ink == 0:
                continue
            mask = (cell == 11) | (cell == 12) | (cell == 1)
            ys, xs = np.nonzero(mask)
            if len(ys) == 0:
                continue
            w = xs.max() - xs.min() + 1
            h = ys.max() - ys.min() + 1
            print(f"  ({r},{c:>2}) {ink:>5} x={xs.min():>2}..{xs.max():<2} "
                  f"y={ys.min():>2}..{ys.max():<2} {w}×{h}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
