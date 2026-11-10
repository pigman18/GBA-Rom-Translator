#!/usr/bin/env python3
"""调研(90) 修掉「跨行」问题 —— 汉字 11px 高，跨 tilemap 两个行。

═══════════════════════════════════════════════════════════════════════════
【(89) 暴露的真相】
═══════════════════════════════════════════════════════════════════════════
按 tilemap「行」渲染，每行只看到半个汉字（上半截或下半截）。
证据：all_rows_6x.png 里每个汉字上下错开，像被切成两半。

⇒ **汉字 11px 高，但 tilemap 每行只有 8px**，
   所以一个汉字跨 tilemap 的第 N 行和第 N+1 行。

这解释了：
  · 行1 tiles=[1,2,3,4,5...] 是汉字的上半
  · 行2 tiles=[25,26,27...] 是同一批汉字的下半
    （25 = 1 + 24，正好是下一行的起点）
  · 我先前以为「1和25是不同字」，其实**是同一个字的上下两半**

【正确拼法】
  汉字 grid 的 (行 r, 列 c) = tilemap 行 2r 和 2r+1 的第 c 列，
  上下拼接成 8+8=16px 高（11px 字形落在其中）。

【本脚本】
 ① 把 tilemap 行 2r / 2r+1 拼成 16px 高的完整汉字行
 ② 按 13px 步进横向切
 ③ 导出干净字库大图

用法：python scripts/research/firered/90_fix_span.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "glyphs"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def tile_nib(vram: bytes, t: int, ly: int) -> np.ndarray:
    """取 tile t 的第 ly 行（8 个 nibble）。"""
    o = t * 32
    if o + 32 > len(vram):
        return np.full(8, 10, dtype=np.uint8)
    rb = vram[o + ly * 4: o + ly * 4 + 4]
    if len(rb) < 4:
        return np.full(8, 10, dtype=np.uint8)
    out = np.zeros(8, dtype=np.uint8)
    for x in range(8):
        b = rb[x // 2]
        out[x] = (b & 0x0F) if x % 2 == 0 else (b >> 4)
    return out


def render_textband(vram: bytes, sb: int, row0: int, row1: int,
                    cols: int = 30) -> np.ndarray:
    """把 tilemap 的 row0 与 row1 垂直拼成 16px 高的一条。"""
    out = np.full((16, cols * 8), 10, dtype=np.uint8)
    for c in range(cols):
        # 上半
        e0 = rd16(vram, sb + (row0 * 32 + c) * 2)
        t0 = e0 & 0x3FF
        for ly in range(8):
            yy = 7 - ly if (e0 >> 11) & 1 else ly
            out[ly, c * 8:(c + 1) * 8] = tile_nib(vram, t0, yy)
        # 下半
        e1 = rd16(vram, sb + (row1 * 32 + c) * 2)
        t1 = e1 & 0x3FF
        for ly in range(8):
            yy = 7 - ly if (e1 >> 11) & 1 else ly
            out[8 + ly, c * 8:(c + 1) * 8] = tile_nib(vram, t1, yy)
    return out


def main() -> int:
    from PIL import Image

    vram = (OUT / "g1.vram.bin").read_bytes()
    sb, cb = 0xF000, 0x0000

    print("=" * 78)
    print("① 把 tilemap 相邻两行拼成完整汉字行")
    print("=" * 78)
    bands = []
    for pair in range(6):
        r0, r1 = pair * 2, pair * 2 + 1
        band = render_textband(vram, sb, r0, r1)
        ink = int(((band == 11) | (band == 12) | (band == 1)).sum())
        print(f"  行带{pair}（tilemap 行 {r0}+{r1}）: 墨量 {ink}")
        bands.append((pair, band, ink))

    # ── ② 导出每行带 ─────────────────────────────────────────────
    def nib_to_rgb(img: np.ndarray) -> np.ndarray:
        out = np.full((*img.shape, 3), 255, dtype=np.uint8)
        out[img == 11] = (150, 150, 150)
        out[img == 12] = (0, 0, 0)
        out[img == 1] = (200, 0, 0)
        # 10 = 白（背景）
        return out

    print("\n" + "=" * 78)
    print("② 导出行带图（放大 6 倍）")
    print("=" * 78)
    imgs = []
    for pair, band, ink in bands:
        if ink < 10:
            continue
        rgb = nib_to_rgb(band)
        imgs.append(rgb)
        big = np.repeat(np.repeat(rgb, 6, axis=0), 6, axis=1)
        p = OUT / f"band{pair}.png"
        Image.fromarray(big).save(p)
        print(f"  行带{pair} → {p.name}  墨量 {ink}")

    if imgs:
        sep = np.full((6, imgs[0].shape[1], 3), 180, dtype=np.uint8)
        merged = []
        for i, im in enumerate(imgs):
            if i:
                merged.append(sep)
            merged.append(im)
        allimg = np.concatenate(merged, axis=0)
        big = np.repeat(np.repeat(allimg, 6, axis=0), 6, axis=1)
        p = OUT / "font_bands_6x.png"
        Image.fromarray(big).save(p)
        print(f"\n  合并 → {p.name} ({big.shape[1]}×{big.shape[0]})")

    # ── ③ 按 13px 切字，导出「字库格」 ───────────────────────────
    print("\n" + "=" * 78)
    print("③ 按 13px 步进切出单个汉字，拼成字库格")
    print("=" * 78)
    PITCH = 13
    GLYPHS = []
    for pair, band, ink in bands:
        if ink < 10:
            continue
        W = band.shape[1]
        x = 0
        while x + PITCH <= W:
            cell = band[:, x:x + PITCH]        # 16 × 13
            m = int(((cell == 11) | (cell == 12) | (cell == 1)).sum())
            if m > 4:
                GLYPHS.append((pair, x, cell, m))
            x += PITCH
    print(f"  切出非空字位 {len(GLYPHS)} 个")

    if GLYPHS:
        # 每行 16 个，排成网格
        N = len(GLYPHS)
        COLS = 16
        ROWS = (N + COLS - 1) // COLS
        CW, CH, GAP = PITCH, 16, 2
        W2 = COLS * (CW + GAP) + GAP
        H2 = ROWS * (CH + GAP) + GAP
        canvas = np.full((H2, W2, 3), 235, dtype=np.uint8)
        for i, (pair, x, cell, m) in enumerate(GLYPHS):
            r, c = i // COLS, i % COLS
            y0 = GAP + r * (CH + GAP)
            x0 = GAP + c * (CW + GAP)
            canvas[y0:y0 + CH, x0:x0 + CW] = nib_to_rgb(cell)
        big = np.repeat(np.repeat(canvas, 4, axis=0), 4, axis=1)
        p = OUT / "font_glyphgrid_4x.png"
        Image.fromarray(big).save(p)
        print(f"  → {p.name}  ({big.shape[1]}×{big.shape[0]})")
        print(f"    {ROWS} 行 × {COLS} 列 = {N} 个字位")

        # 打印前 20 个字的墨量
        print(f"\n  前 20 个字位（行带, x, 墨量）：")
        for pair, x, cell, m in GLYPHS[:20]:
            print(f"    带{pair} x={x:>3}  墨量 {m:>3}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
