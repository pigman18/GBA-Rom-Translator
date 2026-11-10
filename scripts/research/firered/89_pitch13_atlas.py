#!/usr/bin/env python3
"""调研(89) 按真实步进 13px 重切字库 —— 这才是正确排版。

═══════════════════════════════════════════════════════════════════════════
【(88) 的错】
═══════════════════════════════════════════════════════════════════════════
我按「每汉字 2×2 tile = 16×16」切，量出来的墨迹宽 14~16，
因为**汉字不是 16 宽，而是 11 宽、步进 13**。

(85) 已在渲染图上实测：
    段1 x=26..36 (宽 11)，段2 x=39..49，段3 x=52..62
    起点间隔 = 13

⇒ tilemap 里每个汉字占的 tile 不是一个固定 2×2 块，
   而是「按 13px 推进」——13 不是 8 的倍数，所以跨 tile 边界会错位。

这解释了 tile 序号为什么是 1,2,3,4,5（每字一个 tile？）而不是 1,2 / 25,26。

═══════════════════════════════════════════════════════════════════════════
【重新理解 tilemap】
═══════════════════════════════════════════════════════════════════════════
 行1 tiles=[..., 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
 行2 tiles=[..., 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35]

 行1 和行2 的 tile 序号差 24 ⇒ 每行 24 个 tile。
 若一行显示 12 个汉字（继续游戏…），则**每汉字 2 个 tile**。
 但 2 tile 宽 = 16px，而实测步进 13px ⇒ 矛盾。

 除非：**tilemap 的每列不是 8px 而是一个字符格**。
 即 GBA 的 tilemap 一个表项画 8px，但**文字用 13px 步进跨了表项**。

⇒ 结论：不能用「格」去切，必须**按 13px 直接扫像素**重建字串。

【本脚本做法】
 不做格子假设，直接从 VRAM 渲染出一整行像素（240px 宽），
 然后按 13px 步进切出每个字，导出成一张干净的横排字库图。
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "glyphs"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def render_row(vram: bytes, sb: int, cb: int, row: int,
               pitches: int = 30) -> np.ndarray:
    """渲染 tilemap 的一行，返回 (8, pitches*8) nibble 图。"""
    out = np.full((8, pitches * 8), 10, dtype=np.uint8)
    for py in range(8):
        for c in range(pitches):
            eo = sb + (row * 32 + c) * 2
            if eo + 2 > len(vram):
                continue
            ent = rd16(vram, eo)
            tidx = ent & 0x3FF
            ly = 7 - py if (ent >> 11) & 1 else py
            to = cb + tidx * 32
            if to + 32 > len(vram):
                continue
            blob = vram[to:to + 32]
            rb = blob[ly * 4:(ly + 1) * 4]
            for x in range(8):
                b = rb[x // 2]
                p = (b & 0x0F) if x % 2 == 0 else (b >> 4)
                out[py, c * 8 + x] = p if p else 10
    return out


def main() -> int:
    from PIL import Image

    vram = (OUT / "g1.vram.bin").read_bytes()
    sb, cb = 0xF000, 0x0000

    print("=" * 78)
    print("① 渲染 tilemap 前 12 行，找文字行")
    print("=" * 78)
    rows = {}
    for r in range(12):
        img = render_row(vram, sb, cb, r)
        ink = int(((img == 11) | (img == 12) | (img == 1)).sum())
        rows[r] = (img, ink)
        print(f"  行{r:>2}: 墨量 {ink:>4}")

    # ── ② 对每个有墨的行，按 13px 步进切字 ────────────────────────
    print("\n" + "=" * 78)
    print("② 按 13px 步进切字（验证 11 宽 + 2 间距）")
    print("=" * 78)

    def split_by_pitch(img: np.ndarray, pitch: int = 13) -> list[np.ndarray]:
        """把一行按 pitch 切成若干 8×pitch 的块。"""
        W = img.shape[1]
        out = []
        x = 0
        while x + pitch <= W:
            out.append(img[:, x:x + pitch])
            x += pitch
        return out

    for r in range(12):
        img, ink = rows[r]
        if ink < 20:
            continue
        cells = split_by_pitch(img, 13)
        nonempty = []
        for i, c in enumerate(cells):
            m = int(((c == 11) | (c == 12) | (c == 1)).sum())
            if m > 4:
                nonempty.append((i, m))
        print(f"\n  行{r}: 13px 切出 {len(cells)} 格，非空 {len(nonempty)} 个")
        if nonempty:
            print(f"    非空格：(索引, 墨量) = {nonempty[:16]}")

    # ── ③ 导出：每行一张 13px 步进的图 ────────────────────────────
    print("\n" + "=" * 78)
    print("③ 导出每行（按 13px 步进），放大 6 倍")
    print("=" * 78)

    def nib_to_rgb(img: np.ndarray) -> np.ndarray:
        out = np.full((*img.shape, 3), 255, dtype=np.uint8)
        out[img == 11] = (150, 150, 150)
        out[img == 12] = (0, 0, 0)
        out[img == 1] = (200, 0, 0)
        return out

    lines = []
    for r in range(12):
        img, ink = rows[r]
        if ink < 10:
            continue
        rgb = nib_to_rgb(img)
        lines.append(rgb)
        # 单行导出
        big = np.repeat(np.repeat(rgb, 6, axis=0), 6, axis=1)
        p = OUT / f"row{r:02d}.png"
        Image.fromarray(big).save(p)
        print(f"  行{r} → {p.name}")

    # 合并成一张
    if lines:
        sep = np.full((4, lines[0].shape[1], 3), 200, dtype=np.uint8)
        merged = []
        for i, l in enumerate(lines):
            if i:
                merged.append(sep)
            merged.append(l)
        allimg = np.concatenate(merged, axis=0)
        big = np.repeat(np.repeat(allimg, 6, axis=0), 6, axis=1)
        p = OUT / "all_rows_6x.png"
        Image.fromarray(big).save(p)
        print(f"\n  合并 → {p.name} ({big.shape[1]}×{big.shape[0]})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
