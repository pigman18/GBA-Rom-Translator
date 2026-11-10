#!/usr/bin/env python3
"""调研(94) 提取单个汉字，做成标准字库格 —— 一个汉字一张图。

═══════════════════════════════════════════════════════════════════════════
【(93) 已完全成功】
═══════════════════════════════════════════════════════════════════════════
从渲染出的 240×160 画面按 13px 步进切字，得到：

    继续游戏
    主角  RED
    时间  22:04
    图鉴  62只
    徽章  7枚
    开始新游戏

字位坐标（每行）：x = 26, 39, 52, 65, 78, 91（间隔 13）

【本脚本：做成真正的「字库」形态】
 ① 每个汉字裁成独立图片（11×12）
 ② 按原顺序排成网格，每格标编号
 ③ 导出：
     LIB_single_glyphs.png   单字网格（放大 8 倍，清晰）
     LIB_ascii.txt           每个字的 ASCII 点阵（可直接核对字形）
 ④ 统计：一共多少个不同的字位

用法：python scripts/research/firered/94_single_glyphs.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "glyphs"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def render(vram: bytes, sb: int, cb: int):
    idx = np.zeros((160, 240), dtype=np.uint8)
    is_text = np.zeros((160, 240), dtype=bool)
    for py in range(160):
        row = py // 8
        for px in range(240):
            col = px // 8
            eo = sb + (row * 32 + col) * 2
            if eo + 2 > len(vram):
                continue
            ent = rd16(vram, eo)
            tidx = ent & 0x3FF
            pil = (ent >> 12) & 0xF
            ly, lx = py % 8, px % 8
            if (ent >> 11) & 1:
                ly = 7 - ly
            if (ent >> 10) & 1:
                lx = 7 - lx
            to = cb + tidx * 32
            by = to + ly * 4 + lx // 2
            if by >= len(vram):
                continue
            b = vram[by]
            p = (b & 0x0F) if lx % 2 == 0 else (b >> 4)
            if p:
                idx[py, px] = pil * 16 + p
                is_text[py, px] = (pil == 15)
    return idx, is_text


def main() -> int:
    from PIL import Image

    vram = (OUT / "g1.vram.bin").read_bytes()
    idx, is_text = render(vram, 0xF000, 0x0000)
    txt = is_text & ((idx % 16 == 11) | (idx % 16 == 12))

    PITCH = 13
    rowsum = txt.sum(axis=1)
    lines = [y for y in range(160) if rowsum[y] > 2]
    groups = []
    if lines:
        s = p = lines[0]
        for y in lines[1:]:
            if y - p <= 2:
                p = y
            else:
                groups.append((s, p))
                s = p = y
        groups.append((s, p))

    # 收集所有字位
    glyphs = []
    for a, b in groups:
        x = 0
        while x + PITCH <= 240:
            cell = txt[a:b + 1, x:x + PITCH]
            if int(cell.sum()) > 3:
                glyphs.append((a, b, x, cell))
            x += PITCH

    print("=" * 78)
    print(f"① 共 {len(glyphs)} 个字位")
    print("=" * 78)
    for i, (a, b, x, cell) in enumerate(glyphs):
        print(f"  [{i:>2}] y={a}..{b} x={x:>3} 墨 {int(cell.sum()):>3}")

    # ── ② ASCII 点阵输出 ─────────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 每个字的 ASCII 点阵")
    print("=" * 78)
    lines_out = []
    for i, (a, b, x, cell) in enumerate(glyphs):
        h, w = cell.shape
        lines_out.append(f"--- glyph #{i}  y={a}..{b} x={x}  {w}x{h} ---")
        for yy in range(h):
            lines_out.append("".join("#" if cell[yy, xx] else "."
                                     for xx in range(w)))
        lines_out.append("")
        print(f"\n  #{i}  ({w}×{h})")
        for yy in range(h):
            print("    " + "".join("#" if cell[yy, xx] else "."
                                   for xx in range(w)))

    (OUT / "LIB_ascii.txt").write_text("\n".join(lines_out), encoding="utf-8")
    print(f"\n  已写 LIB_ascii.txt")

    # ── ③ 单字网格图 ─────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 单字网格图")
    print("=" * 78)
    if not glyphs:
        return 0
    COLS = 8
    N = len(glyphs)
    ROWS = (N + COLS - 1) // COLS
    # 统一格子尺寸
    CW, CH = PITCH, max(g[3].shape[0] for g in glyphs)
    GAP = 3
    W = COLS * (CW + GAP) + GAP
    H = ROWS * (CH + GAP) + GAP
    canvas = np.full((H, W, 3), 245, dtype=np.uint8)
    for i, (a, b, x, cell) in enumerate(glyphs):
        r, c = i // COLS, i % COLS
        y0 = GAP + r * (CH + GAP)
        x0 = GAP + c * (CW + GAP)
        for yy in range(cell.shape[0]):
            for xx in range(cell.shape[1]):
                if cell[yy, xx]:
                    canvas[y0 + yy, x0 + xx] = (0, 0, 0)
        # 边框
        canvas[y0 - 1, x0 - 1:x0 + CW + 1] = (160, 160, 220)
        canvas[y0 + CH, x0 - 1:x0 + CW + 1] = (160, 160, 220)
        canvas[y0 - 1:y0 + CH + 1, x0 - 1] = (160, 160, 220)
        canvas[y0 - 1:y0 + CH + 1, x0 + CW] = (160, 160, 220)

    big = np.repeat(np.repeat(canvas, 8, axis=0), 8, axis=1)
    p = OUT / "LIB_single_glyphs.png"
    Image.fromarray(big).save(p)
    print(f"  → {p.name}  ({big.shape[1]}×{big.shape[0]})")
    print(f"    {ROWS} 行 × {COLS} 列 = {N} 个字位，每格 {CW}×{CH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
