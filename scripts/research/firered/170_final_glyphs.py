#!/usr/bin/env python3
"""调研(170) 修正切法：每个汉字 = 2 个 tile 宽 × 2 行高（16×16 里的 11×11）。

═══════════════════════════════════════════════════════════════════════════
【(169) 的结果与问题】
═══════════════════════════════════════════════════════════════════════════
✅ 成功切出 9 个汉字，能辨认「继续…戏 / 开始新游戏」
❌ 但字形被**压扁**了：我只按 13px 步进横向切，没有正确处理「2 tile 宽」

【正确理解】
 tilemap 行 1 的 pal=15 tile 是 col3..col9 共 7 个（tile 1..7），
 而「继续游戏」是 4 个汉字 → **每汉字约 1.75 个 tile**？

 更可能的解释：
   · 每汉字占 2 个 tile（16px 空间），但**显示步进 13px**（重叠 3px）
   · 所以 4 个汉字需要 4×13=52px ≈ 7 个 tile（56px）✓ 与实测吻合

 ⇒ 正确切法：横向按 **13px 像素**切（而不是按 tile），
   纵向按 **2 行 tile = 16px** 切。

 (169) 的纵向我做对了（拼了 2 行），横向按 13px 也对，
 但**起始 x 没对齐**（我从 x=0 开始，应该从第一个非空像素开始）。

【本脚本】
 ① 拼出 tilemap 行 2k + 2k+1 的完整 16 行画布
 ② 自动找第一个非空列作为起点
 ③ 按 13px 步进切，导出每个字的独立 PNG（放大）
 ④ 标注每个字的位置，便于人工核对

用法：python scripts/research/firered/170_final_glyphs.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            b = blob[y * 4 + x // 2]
            m[y, x] = (b & 0x0F) if x % 2 == 0 else (b >> 4)
    return m


def main() -> int:
    vr = (SNAP / "vram.bin").read_bytes()
    SB = 0xF000

    # ── 找到所有文字带（相邻两行一组）──────────────────
    def row_ink(r: int) -> int:
        n = 0
        for c in range(30):
            e = rd16(vr, SB + (r * 32 + c) * 2)
            if ((e >> 12) & 0xF) != 15:
                continue
            off = (e & 0x3FF) * 32
            if off + 32 > len(vr):
                continue
            u = set(v for b in vr[off:off + 32] for v in (b & 0xF, b >> 4))
            if u & {11, 12}:
                n += 1
        return n

    text_rows = [r for r in range(20) if row_ink(r) > 0]
    print(f"有文字的 tilemap 行：{text_rows}")

    # 两行一组
    bands = []
    i = 0
    while i < len(text_rows):
        r = text_rows[i]
        r2 = r + 1 if (i + 1 < len(text_rows) and text_rows[i + 1] == r + 1) else None
        bands.append((r, r2))
        i += 2 if r2 else 1

    print(f"分成 {len(bands)} 条文字带：{bands}")

    all_glyphs = []
    for r, r2 in bands:
        rows = [r] + ([r2] if r2 else [])
        cv = np.full((len(rows) * 8, 240), 10, dtype=np.uint8)
        for yi, rr in enumerate(rows):
            for c in range(30):
                e = rd16(vr, SB + (rr * 32 + c) * 2)
                if ((e >> 12) & 0xF) != 15:
                    continue
                off = (e & 0x3FF) * 32
                if off + 32 > len(vr):
                    continue
                cv[yi * 8:(yi + 1) * 8, c * 8:(c + 1) * 8] = \
                    nibs(vr[off:off + 32])

        ink = (cv == 11) | (cv == 12)
        cols = np.flatnonzero(ink.any(axis=0))
        if len(cols) == 0:
            continue
        x0, x1 = int(cols[0]), int(cols[-1])
        print(f"\n带 {r}" + (f"+{r2}" if r2 else "") +
              f"：墨迹列 x={x0}..{x1}（宽 {x1-x0+1}）")

        # 找起点：x0 向下取 13 的倍数会有偏移，直接用 x0
        PITCH = 13
        x = x0
        n = 0
        while x + PITCH <= x1 + 4:
            cell = cv[:, x:x + PITCH]
            m = int(((cell == 11) | (cell == 12)).sum())
            if m > 4:
                all_glyphs.append((r, x, cell, m))
                n += 1
            x += PITCH
        print(f"  切出 {n} 个字")

    print(f"\n共 {len(all_glyphs)} 个字位")

    # ── 导出 PNG（每个字单独一格，放大 8 倍）──────────
    try:
        from PIL import Image
        if not all_glyphs:
            return 0
        COLS = 8
        N = len(all_glyphs)
        ROWS = (N + COLS - 1) // COLS
        CH = max(g[2].shape[0] for g in all_glyphs)
        CW = 13
        GAP = 3
        W = COLS * (CW + GAP) + GAP
        H = ROWS * (CH + GAP) + GAP
        canvas = np.full((H, W, 3), 250, dtype=np.uint8)
        for i, (r, x, cell, m) in enumerate(all_glyphs):
            rr, cc = i // COLS, i % COLS
            y0 = GAP + rr * (CH + GAP)
            x0 = GAP + cc * (CW + GAP)
            for yy in range(min(CH, cell.shape[0])):
                for xx in range(CW):
                    v = cell[yy, xx]
                    if v == 12:
                        canvas[y0 + yy, x0 + xx] = (0, 0, 0)
                    elif v == 11:
                        canvas[y0 + yy, x0 + xx] = (150, 150, 150)
            canvas[y0 - 1, x0 - 1:x0 + CW + 1] = (170, 170, 220)
            canvas[y0 + CH, x0 - 1:x0 + CW + 1] = (170, 170, 220)
            canvas[y0 - 1:y0 + CH + 1, x0 - 1] = (170, 170, 220)
            canvas[y0 - 1:y0 + CH + 1, x0 + CW] = (170, 170, 220)
        big = np.repeat(np.repeat(canvas, 8, axis=0), 8, axis=1)
        p = SNAP / "GLYPHS_FINAL.png"
        Image.fromarray(big).save(p)
        print(f"→ {p.name}  ({big.shape[1]}×{big.shape[0]})")

        # 也导出全行（保持原顺序）
        allw = 0
        for r, r2 in bands:
            pass
        print(f"  字位列表：")
        for i, (r, x, cell, m) in enumerate(all_glyphs):
            print(f"    [{i:>2}] 行{r} x={x:>3} 墨{m:>3}")
    except ImportError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
