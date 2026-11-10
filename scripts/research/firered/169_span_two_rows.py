#!/usr/bin/env python3
"""调研(169) 定案：字形 = 相邻两条 tilemap 行拼起来（上 5 行 + 下 5 行）。

═══════════════════════════════════════════════════════════════════════════
【(168) 的精确观察】
═══════════════════════════════════════════════════════════════════════════
tilemap 行1 的 pal=15 tile：
   col3 tile=1  nibble={10,11,12}  前 3 行空，后 5 行有笔画
   col4 tile=2  同上
   col5 tile=3  同上
   col6 tile=4  同上
   col7 tile=5  同上
   col8 tile=6  同上
   col9 tile=7  同上
   col10 tile=8 nibble={10} 全空（内容结束）

⇒ 一行的文字占 **col3..col9 共 7 个 tile**，且**每块只有 5 行有笔画**。
   col2 是边框（pal=2）。

而 tilemap 行2 的 tile 是 25,26,...（与行1的 1,2,... 差 24）
⇒ **行2 是同一批汉字的「下半」**。

【所以正确的拼法】
  汉字 = tilemap 行 N 的 tile + 行 N+1 的 tile，上下叠成 16 行
  其中上 8 行只用了后 5 行（前 3 行留白），下 8 行用前 5 行
  ⇒ 实际字形高度 = 3(空) + 5 + 5 = 13 行？不对，应该直接拼：

     行N 的 tile（8 行，后 5 行有墨）
     行N+1 的 tile（8 行，前 5 行有墨）
     → 拼成 16 行，有效笔画在 8..12 和 8..12 之间

【本脚本】
 ① 把 tilemap 行 2k 与 2k+1 的 pal=15 tile 上下拼成 16 行
 ② 按 13px 步进切字
 ③ 导出字库图

用法：python scripts/research/firered/169_span_two_rows.py
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


def ch(v: int) -> str:
    if v in (0, 10):
        return " "
    if v == 12:
        return "#"
    if v == 11:
        return "+"
    return str(v)


def main() -> int:
    vr = (SNAP / "vram.bin").read_bytes()
    SB = 0xF000

    print("=" * 78)
    print("① 找出所有「pal=15 且非全空」的 tilemap 行")
    print("=" * 78)
    rows = []
    for r in range(20):
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
        if n:
            rows.append((r, n))
    print(f"  有笔画的 tilemap 行：{[(r, n) for r, n in rows]}")

    # ── ② 两行拼一起渲染 ──────────────────────────────
    print("\n" + "=" * 78)
    print("② 相邻两行拼成 16 行渲染")
    print("=" * 78)
    used = {r for r, _ in rows}
    bands = []
    for r in sorted(used):
        if r - 1 in used:
            continue          # 只从每组的首行开始
        r2 = r + 1
        if r2 not in used:
            r2 = None
        canvas = np.full((16 if r2 else 8, 30 * 8), 10, dtype=np.uint8)
        for y_row, rr in enumerate([r] + ([r2] if r2 else [])):
            for c in range(30):
                e = rd16(vr, SB + (rr * 32 + c) * 2)
                if ((e >> 12) & 0xF) != 15:
                    continue
                off = (e & 0x3FF) * 32
                if off + 32 > len(vr):
                    continue
                canvas[y_row * 8:(y_row + 1) * 8, c * 8:(c + 1) * 8] = \
                    nibs(vr[off:off + 32])
        bands.append((r, r2, canvas))

    for r, r2, cv in bands:
        print(f"\n  === 行 {r}" + (f"+{r2}" if r2 else "") +
              f"  ({cv.shape[0]} 行) ===")
        # 只画前 20 列（160px）
        for y in range(cv.shape[0]):
            line = "".join(ch(cv[y, x]) for x in range(160))
            if line.strip():
                print(f"    |{line}|")

    # ── ③ 按 13px 步进切字，导出 ──────────────────────
    print("\n" + "=" * 78)
    print("③ 按 13px 步进切字")
    print("=" * 78)
    PITCH = 13
    glyphs = []
    for r, r2, cv in bands:
        W = cv.shape[1]
        x = 0
        while x + PITCH <= W:
            cell = cv[:, x:x + PITCH]
            ink = int(((cell == 11) | (cell == 12)).sum())
            if ink > 4:
                glyphs.append((r, x, cell, ink))
            x += PITCH
    print(f"  切出 {len(glyphs)} 个字位")
    for r, x, cell, ink in glyphs[:20]:
        print(f"    行{r} x={x:>3}  墨量 {ink}")

    # ── ④ 导出 PNG ───────────────────────────────────
    try:
        from PIL import Image
        if glyphs:
            COLS = 10
            N = len(glyphs)
            ROWS = (N + COLS - 1) // COLS
            CW, CH = PITCH, 16
            GAP = 2
            W = COLS * (CW + GAP) + GAP
            H = ROWS * (CH + GAP) + GAP
            canvas = np.full((H, W, 3), 245, dtype=np.uint8)
            for i, (r, x, cell, ink) in enumerate(glyphs):
                rr, cc = i // COLS, i % COLS
                y0 = GAP + rr * (CH + GAP)
                x0 = GAP + cc * (CW + GAP)
                for yy in range(min(CH, cell.shape[0])):
                    for xx in range(CW):
                        v = cell[yy, xx]
                        if v == 12:
                            canvas[y0 + yy, x0 + xx] = (0, 0, 0)
                        elif v == 11:
                            canvas[y0 + yy, x0 + xx] = (160, 160, 160)
            big = np.repeat(np.repeat(canvas, 6, axis=0), 6, axis=1)
            p = SNAP / "GLYPHS_FROM_VRAM.png"
            Image.fromarray(big).save(p)
            print(f"\n  → {p.name}  ({big.shape[1]}×{big.shape[0]})")
            print(f"    {N} 个字位，{ROWS} 行 × {COLS} 列")
    except ImportError:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
