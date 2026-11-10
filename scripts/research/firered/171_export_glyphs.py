#!/usr/bin/env python3
"""调研(171) 定案：字形真实尺寸 13×12，导出干净字库。

═══════════════════════════════════════════════════════════════════════════
【(170) 的精确测量】
═══════════════════════════════════════════════════════════════════════════
文字带（tilemap 行 1+2 拼 16 行）的**逐行墨量**：

    y=0..2    : 0   （空白）
    y=3..14   : 20..47（有笔画，共 12 行）
    y=15      : 0   （空白）

⇒ **字形真实高度 = 12 行**（y=3..14）
⇒ 横向：每字 13px（x=26,39,52,65，步进 13）

**所以字形是 13 宽 × 12 高的格子，墨迹在其中。**

第一个字的点阵（「继」）：
    y=3  |  +#+# +#    |
    y=4  | +##++#+#+#  |
    ...
    y=14 |##  ######## |
    → 绞丝旁三折清晰、右侧「米」结构完整 ⇒ **确认是「继」**

【本脚本】
 ① 对每条文字带，按 y=3..14 裁出 12 行
 ② 按 13px 横向切
 ③ 导出最终字库（放大、无多余空白）
 ④ 同时输出每个字的 ASCII 点阵到文本

用法：python scripts/research/firered/171_export_glyphs.py
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

    def row_has_ink(r: int) -> bool:
        for c in range(30):
            e = rd16(vr, SB + (r * 32 + c) * 2)
            if ((e >> 12) & 0xF) != 15:
                continue
            off = (e & 0x3FF) * 32
            if off + 32 > len(vr):
                continue
            u = set(v for b in vr[off:off + 32] for v in (b & 0xF, b >> 4))
            if u & {11, 12}:
                return True
        return False

    text_rows = [r for r in range(20) if row_has_ink(r)]
    bands = []
    i = 0
    while i < len(text_rows):
        r = text_rows[i]
        r2 = (r + 1 if i + 1 < len(text_rows) and
              text_rows[i + 1] == r + 1 else None)
        bands.append((r, r2))
        i += 2 if r2 else 1

    PITCH = 13
    glyphs = []
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
        ys = np.flatnonzero(ink.any(axis=1))
        if len(ys) == 0:
            continue
        y0, y1 = int(ys[0]), int(ys[-1])
        xs = np.flatnonzero(ink.any(axis=0))
        x0 = int(xs[0])
        x1 = int(xs[-1])
        # 统一裁到 12 行（若不足补白）
        H = 12
        core = cv[y0:y0 + H] if y0 + H <= cv.shape[0] else cv[y0:]
        if core.shape[0] < H:
            core = np.vstack([core,
                              np.full((H - core.shape[0], 240), 10,
                                      dtype=np.uint8)])
        x = x0
        while x + PITCH <= x1 + 4:
            cell = core[:, x:x + PITCH]
            m = int(((cell == 11) | (cell == 12)).sum())
            if m > 4:
                glyphs.append((r, x, cell, m))
            x += PITCH

    print("=" * 78)
    print(f"共 {len(glyphs)} 个字位，每字 {PITCH}×12")
    print("=" * 78)

    # ASCII 输出
    lines_txt = []
    for i, (r, x, cell, m) in enumerate(glyphs):
        lines_txt.append(f"--- #{i} 行{r} x={x} 墨{m} ---")
        for y in range(cell.shape[0]):
            rowtxt = "".join(
                "#" if cell[y, xx] == 12 else ("+" if cell[y, xx] == 11
                                               else ".")
                for xx in range(PITCH))
            lines_txt.append(rowtxt)
        lines_txt.append("")
        if i < 8:
            print(f"\n#{i} 行{r} x={x} 墨{m}")
            for y in range(cell.shape[0]):
                print("  " + "".join(
                    "#" if cell[y, xx] == 12 else
                    ("+" if cell[y, xx] == 11 else ".")
                    for xx in range(PITCH)))
    (SNAP / "glyphs_ascii.txt").write_text("\n".join(lines_txt),
                                            encoding="utf-8")

    # PNG
    try:
        from PIL import Image
        COLS = 8
        N = len(glyphs)
        ROWS = (N + COLS - 1) // COLS
        CH, CW, GAP = 12, PITCH, 3
        W = COLS * (CW + GAP) + GAP
        H = ROWS * (CH + GAP) + GAP
        canvas = np.full((H, W, 3), 252, dtype=np.uint8)
        for i, (r, x, cell, m) in enumerate(glyphs):
            rr, cc = i // COLS, i % COLS
            y0c = GAP + rr * (CH + GAP)
            x0c = GAP + cc * (CW + GAP)
            for yy in range(CH):
                for xx in range(CW):
                    v = cell[yy, xx]
                    if v == 12:
                        canvas[y0c + yy, x0c + xx] = (0, 0, 0)
                    elif v == 11:
                        canvas[y0c + yy, x0c + xx] = (150, 150, 150)
            canvas[y0c - 1, x0c - 1:x0c + CW + 1] = (180, 180, 225)
            canvas[y0c + CH, x0c - 1:x0c + CW + 1] = (180, 180, 225)
            canvas[y0c - 1:y0c + CH + 1, x0c - 1] = (180, 180, 225)
            canvas[y0c - 1:y0c + CH + 1, x0c + CW] = (180, 180, 225)
        big = np.repeat(np.repeat(canvas, 8, axis=0), 8, axis=1)
        p = SNAP / "GLYPHS_CLEAN.png"
        Image.fromarray(big).save(p)
        print(f"\n→ {p.name}  ({big.shape[1]}×{big.shape[0]})")
        print(f"→ glyphs_ascii.txt")
    except ImportError:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
