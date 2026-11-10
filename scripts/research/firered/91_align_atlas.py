#!/usr/bin/env python3
"""调研(91) 精确对齐：找到汉字的真实垂直起点，输出干净字库。

═══════════════════════════════════════════════════════════════════════════
【现状】
═══════════════════════════════════════════════════════════════════════════
(90) 已能把相邻两行 tilemap 拼成 16px 高的行带，字库内容对：
    继续游戏 / 主角 RED / 时间 22:04 / 图鉴 62只 / 徽章 7枚 / 开始新游戏

但字库里**上下仍错半格**：汉字墨迹在 16px 格里的 y=3..14，
而下一行带的起点没对齐到 3，导致看起来错位。

【本脚本：先量，再切】
 ① 对每条行带，逐行统计墨量，找出墨迹的真实 y 起点和高度
 ② 用这个偏移去切，保证每个字都在格子中央
 ③ 导出最终字库图（网格 + 无网格两版）

用法：python scripts/research/firered/91_align_atlas.py
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


def band(vram: bytes, sb: int, r0: int, r1: int, cols: int = 30) -> np.ndarray:
    out = np.full((16, cols * 8), 10, dtype=np.uint8)
    for c in range(cols):
        e0 = rd16(vram, sb + (r0 * 32 + c) * 2)
        t0 = e0 & 0x3FF
        for ly in range(8):
            yy = 7 - ly if (e0 >> 11) & 1 else ly
            out[ly, c * 8:(c + 1) * 8] = tile_nib(vram, t0, yy)
        e1 = rd16(vram, sb + (r1 * 32 + c) * 2)
        t1 = e1 & 0x3FF
        for ly in range(8):
            yy = 7 - ly if (e1 >> 11) & 1 else ly
            out[8 + ly, c * 8:(c + 1) * 8] = tile_nib(vram, t1, yy)
    return out


def main() -> int:
    from PIL import Image

    vram = (OUT / "g1.vram.bin").read_bytes()
    sb = 0xF000

    def is_ink(a):
        return (a == 11) | (a == 12) | (a == 1)

    print("=" * 78)
    print("① 每条行带的墨迹垂直范围")
    print("=" * 78)
    bands = []
    for pair in range(6):
        b = band(vram, sb, pair * 2, pair * 2 + 1)
        ink = is_ink(b)
        rowsum = ink.sum(axis=1)
        ys = np.nonzero(rowsum)[0]
        if len(ys) == 0:
            print(f"  带{pair}: 空")
            continue
        print(f"  带{pair}: y={ys.min()}..{ys.max()} "
              f"(高 {ys.max()-ys.min()+1})  墨量 {int(ink.sum())}")
        print(f"        每行墨量: {rowsum.tolist()}")
        bands.append((pair, b, int(ys.min()), int(ys.max())))

    # ── ② 用真实 y 偏移切字 ───────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 按真实 y 起点切字（每字 16×13）")
    print("=" * 78)
    PITCH = 13
    GLYPHS = []
    for pair, b, y0, y1 in bands:
        H = b.shape[0]
        # 裁出墨迹所在的高度，再补白到 16
        top = max(0, y0 - 2)
        bot = min(H, y1 + 3)
        core = b[top:bot]
        if core.shape[0] < 12:
            pad_top = (12 - core.shape[0]) // 2
            core = np.vstack([
                np.full((pad_top, core.shape[1]), 10, dtype=np.uint8),
                core,
                np.full((12 - core.shape[0] - pad_top, core.shape[1]), 10,
                        dtype=np.uint8)])
        W = b.shape[1]
        x = 0
        while x + PITCH <= W:
            cell = core[:, x:x + PITCH]
            m = int(is_ink(cell).sum())
            if m > 4:
                GLYPHS.append((pair, x, cell, m))
            x += PITCH

    print(f"  切出 {len(GLYPHS)} 个字位")
    for pair in range(6):
        n = sum(1 for g in GLYPHS if g[0] == pair)
        ms = [g[3] for g in GLYPHS if g[0] == pair]
        print(f"    带{pair}: {n} 个字位  墨量 {ms}")

    # ── ③ 导出最终字库 ────────────────────────────────────────────
    if not GLYPHS:
        print("  没有字位")
        return 0

    def to_rgb(img):
        out = np.full((*img.shape, 3), 255, dtype=np.uint8)
        out[img == 11] = (150, 150, 150)
        out[img == 12] = (0, 0, 0)
        out[img == 1] = (200, 0, 0)
        return out

    # 按原始行带分组导出，保持语义
    print("\n" + "=" * 78)
    print("③ 导出最终字库")
    print("=" * 78)

    # 逐条行带导出（保留文字顺序）
    row_imgs = []
    for pair in range(6):
        b = band(vram, sb, pair * 2, pair * 2 + 1)
        ink = is_ink(b)
        if ink.sum() < 10:
            continue
        row_imgs.append(to_rgb(b))

    if row_imgs:
        sep = np.full((4, row_imgs[0].shape[1], 3), 160, dtype=np.uint8)
        merged = []
        for i, im in enumerate(row_imgs):
            if i:
                merged.append(sep)
            merged.append(im)
        allimg = np.concatenate(merged, axis=0)
        big = np.repeat(np.repeat(allimg, 6, axis=0), 6, axis=1)
        p = OUT / "FONT_final_rows.png"
        Image.fromarray(big).save(p)
        print(f"  → {p.name}  ({big.shape[1]}×{big.shape[0]})")

    # 字库格版本
    COLS = 12
    N = len(GLYPHS)
    ROWS = (N + COLS - 1) // COLS
    CH, CW, GAP = GLYPHS[0][2].shape[0], PITCH, 2
    W2 = COLS * (CW + GAP) + GAP
    H2 = ROWS * (CH + GAP) + GAP
    canvas = np.full((H2, W2, 3), 230, dtype=np.uint8)
    for i, (pair, x, cell, m) in enumerate(GLYPHS):
        r, c = i // COLS, i % COLS
        y = GAP + r * (CH + GAP)
        xx = GAP + c * (CW + GAP)
        canvas[y:y + cell.shape[0], xx:xx + CW] = to_rgb(cell)
        canvas[y, xx:xx + CW] = (170, 170, 255)
        canvas[y + cell.shape[0] - 1, xx:xx + CW] = (170, 170, 255)
        canvas[y:y + cell.shape[0], xx] = (170, 170, 255)
        canvas[y:y + cell.shape[0], xx + CW - 1] = (170, 170, 255)
    big = np.repeat(np.repeat(canvas, 5, axis=0), 5, axis=1)
    p2 = OUT / "FONT_final_grid.png"
    Image.fromarray(big).save(p2)
    print(f"  → {p2.name}  ({big.shape[1]}×{big.shape[0]})")
    print(f"    {ROWS} 行 × {COLS} 列 = {N} 个字位")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
