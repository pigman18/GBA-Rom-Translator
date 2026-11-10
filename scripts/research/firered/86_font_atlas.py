#!/usr/bin/env python3
"""调研(86) 抓字库：确认汉字字形在 VRAM 的哪块、怎么排布。

═══════════════════════════════════════════════════════════════════════════
【已知】
═══════════════════════════════════════════════════════════════════════════
  · 汉字 11×11，步进 13
  · tilemap 文字行 tile 序号：1,2,3,4,5 / 25,26,27… 连续递增
  · VRAM 0x0000..0x2000 全是 0xAA（palette15 索引10 = 白）
  · 0xF000 是真实 tilemap

⇒ 若一个汉字用 2×2 tile（16×16 空间装 11×11），
  则 tile 1,2 是上半、tile 25,26 是下半（因为 1+24=25，正好差 24 = 一行 24 个 tile）。

【为什么差 24】
  GBA 的 4bpp tile 是 32 字节，一「行」tile map 若按 30 列排，则 +30。
  但这里差 24 —— 说明**字形是按 24 列宽的图集排的**。

本脚本：
 ① 验证「tile n 与 tile n+24 是同一汉字的上下两半」
 ② 若成立，把 0x0000..0x2000 按 24 列 × N 行拼成一张大图导出
 ③ 用 palette 15 上色（文字色）
 ④ 输出 PNG，人眼直接看字库

用法：python scripts/research/firered/86_font_atlas.py
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
    """取 4bpp tile 的 8×8 nibble 矩阵。"""
    o = t * 32
    if o + 32 > len(vram):
        return np.zeros((8, 8), dtype=np.uint8)
    blob = vram[o:o + 32]
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            b = blob[y * 4 + x // 2]
            m[y, x] = (b & 0x0F) if x % 2 == 0 else (b >> 4)
    return m


def main() -> int:
    from PIL import Image

    vram = (OUT / "g1.vram.bin").read_bytes()
    pal = (OUT / "g1.pal.bin").read_bytes()

    print("=" * 78)
    print("① 验证 tile n 与 n+24 的配对关系")
    print("=" * 78)
    # 文字行 tile: 1,2,3,4,5... 和 25,26,27...（差 24）
    for t in (1, 2, 3):
        a = tile_nibbles(vram, t)
        b = tile_nibbles(vram, t + 24)
        print(f"\n  tile {t} 与 tile {t+24}：")
        for y in range(8):
            la = "".join(f"{v:X}" for v in a[y])
            lb = "".join(f"{v:X}" for v in b[y])
            print(f"    {la}   |   {lb}")

    # ── ② 检查 24 列假设：tile 编号 0..K 按 24 列排 ──────────────
    print("\n" + "=" * 78)
    print("② 用「24 列宽」把 0x0000..0x2000 的 tile 拼成图集")
    print("=" * 78)
    # 0x0000..0x2000 = 256 个 tile（32B each）
    N = 256
    COLS = 24
    ROWS = (N + COLS - 1) // COLS
    # 每个「汉字」占 2×2 tile => 实际是 24 列 / 2 = 12 个汉字一行
    print(f"  {N} 个 tile，按 {COLS} 列排 => {ROWS} 行 tile "
          f"=> 每行 {COLS//2} 个汉字，共 {ROWS//2} 行汉字")

    atlas = np.zeros((ROWS * 8, COLS * 8), dtype=np.uint8)
    for t in range(N):
        r, c = t // COLS, t % COLS
        atlas[r * 8:(r + 1) * 8, c * 8:(c + 1) * 8] = tile_nibbles(vram, t)

    # 用 palette 15 上色
    colors = []
    for i in range(256):
        v = rd16(pal, i * 2) if (i * 2 + 2) <= len(pal) else 0
        colors.append(((v & 0x1F) * 255 // 31,
                       ((v >> 5) & 0x1F) * 255 // 31,
                       ((v >> 10) & 0x1F) * 255 // 31))
    colors = np.array(colors, dtype=np.uint8)

    # 用 palette 15 的映射（索引 = 15*16 + nibble）
    rgb = colors[15 * 16 + atlas]
    p = OUT / "font_atlas_24col.png"
    Image.fromarray(rgb).save(p)
    print(f"  已导出 {p}  ({rgb.shape[1]}×{rgb.shape[0]})")

    # ── ③ 也试其它列宽，各导一张，人眼挑 ────────────────────────
    print("\n" + "=" * 78)
    print("③ 试多种列宽，各导出一张（人眼挑最规整的）")
    print("=" * 78)
    for cols in (16, 20, 24, 28, 30, 32):
        n = 256
        rows = (n + cols - 1) // cols
        im = np.zeros((rows * 8, cols * 8), dtype=np.uint8)
        for t in range(n):
            r, c = t // cols, t % cols
            im[r * 8:(r + 1) * 8, c * 8:(c + 1) * 8] = tile_nibbles(vram, t)
        rgb2 = colors[15 * 16 + im]
        p2 = OUT / f"font_atlas_{cols}col.png"
        Image.fromarray(rgb2).save(p2)
        print(f"  {cols} 列 → {p2.name}  ({im.shape[1]}×{im.shape[0]})")

    # ── ④ 把整块 VRAM 有数据的地方都拼出来（0x0000..0x2000）──────
    print("\n" + "=" * 78)
    print("④ 统计：哪些 tile 的 nibble 值不是 0/10（10=白）")
    print("=" * 78)
    interesting = []
    for t in range(N):
        m = tile_nibbles(vram, t)
        u = set(m.flatten().tolist())
        if u - {0, 10}:
            interesting.append((t, sorted(u)))
    print(f"  有「非白非空」nibble 的 tile：{len(interesting)}")
    for t, u in interesting[:20]:
        print(f"    tile {t}: nibble 值 {u}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
