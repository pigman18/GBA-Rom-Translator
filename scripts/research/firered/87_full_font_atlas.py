#!/usr/bin/env python3
"""调研(87) 抓完整字库大图 —— 扫全 VRAM，找所有字形块并拼成一张大图。

═══════════════════════════════════════════════════════════════════════════
【突破：24 列排布已验证】
═══════════════════════════════════════════════════════════════════════════
(86) 用 24 列把 VRAM 0x0000..0x2000 拼出来，直接读出了：

    继续游戏
    主角  RED
    时间  22:04
    图鉴  62只
    徽章  7枚
    开始新游戏

⇒ 字形确实在 VRAM 0x0000..0x2000，按 **24 列**排。
  每个汉字 = 2×2 tile（16×16 空间放 11×11 字形）。
  所以每行 12 个汉字、每个汉字占 16×16 像素 = 24 列 tile。

【本脚本要做的事】
 ① 扫全 VRAM（0x0000..0x18000）找所有「有字形数据」的 block
 ② 每个 block 按 24 列 × 2 行 tile 切成汉字网格
 ③ 拼成一张**大字库图**，放大 3 倍导出
 ④ 同时导出「纯字形版」（去掉白底，只留笔画），方便辨认

用法：python scripts/research/firered/87_full_font_atlas.py
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


def main() -> int:
    from PIL import Image

    vram = (OUT / "g1.vram.bin").read_bytes()
    pal = (OUT / "g1.pal.bin").read_bytes()

    # 调色板 15 的 16 色
    colors = []
    for i in range(256):
        v = rd16(pal, i * 2) if (i * 2 + 2) <= len(pal) else 0
        colors.append(((v & 0x1F) * 255 // 31,
                       ((v >> 5) & 0x1F) * 255 // 31,
                       ((v >> 10) & 0x1F) * 255 // 31))
    colors = np.array(colors, dtype=np.uint8)

    print("=" * 78)
    print("① 扫全 VRAM，找有字形数据的区域")
    print("=" * 78)
    total_tiles = len(vram) // 32
    print(f"  VRAM 共 {total_tiles} 个 4bpp tile")

    # 字形判据：nibble 里有 11 或 12（浅灰/深灰），而不是只有 0/10（白）
    glyph_tiles = []
    for t in range(total_tiles):
        m = tile_nibbles(vram, t)
        u = set(m.flatten().tolist())
        if u & {11, 12}:
            glyph_tiles.append(t)
    print(f"  含灰阶（11/12）的 tile：{len(glyph_tiles)}")
    if glyph_tiles:
        print(f"    范围 {min(glyph_tiles)} .. {max(glyph_tiles)}")
        # 聚成区间
        runs = []
        s = p = glyph_tiles[0]
        for x in glyph_tiles[1:]:
            if x <= p + 2:
                p = x
            else:
                runs.append((s, p))
                s = p = x
        runs.append((s, p))
        print(f"    聚成 {len(runs)} 段：")
        for a, b in runs:
            print(f"      tile {a}..{b}  (0x{a*32:05X}..0x{(b+1)*32:05X})")

    # ── ② 按 24 列拼大字库 ────────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 按 24 列 (每行 12 个汉字) 拼字库")
    print("=" * 78)

    def build_atlas(start_tile: int, end_tile: int,
                    cols: int = 24) -> tuple[np.ndarray, int]:
        """把 [start, end) 的 tile 按 cols 列排成图。"""
        n = end_tile - start_tile
        rows = (n + cols - 1) // cols
        buf = np.full((rows * 8, cols * 8), 10, dtype=np.uint8)  # 10 = 白
        for i in range(n):
            t = start_tile + i
            r, c = i // cols, i % cols
            buf[r * 8:(r + 1) * 8, c * 8:(c + 1) * 8] = tile_nibbles(vram, t)
        return buf, rows

    # 主字库：0x0000 起 256 个 tile（已证实）
    buf, rows = build_atlas(0, 256, 24)
    rgb = colors[15 * 16 + buf]
    # 放大 4 倍
    big = np.repeat(np.repeat(rgb, 4, axis=0), 4, axis=1)
    p = OUT / "font_big_4x.png"
    Image.fromarray(big).save(p)
    print(f"  主字库 0x0000..0x2000 → {p.name} ({big.shape[1]}×{big.shape[0]})")
    print(f"    {rows} 行 tile = {rows//2} 行汉字 × 12 列")

    # ── ③ 纯字形版：白底改黑底，灰阶保留 ─────────────────────────
    print("\n" + "=" * 78)
    print("③ 纯字形版（黑底白字，方便辨认）")
    print("=" * 78)

    def glyph_only(buf: np.ndarray) -> np.ndarray:
        """nibble 10(白)→黑，11(浅灰)/12(深灰)→亮色。
        0 → 也当黑（空）。"""
        out = np.zeros((*buf.shape, 3), dtype=np.uint8)
        m11 = buf == 11
        m12 = buf == 12
        m1 = buf == 1
        out[m11] = (120, 120, 120)
        out[m12] = (255, 255, 255)
        out[m1] = (255, 200, 0)
        return out

    dark = glyph_only(buf)
    big2 = np.repeat(np.repeat(dark, 4, axis=0), 4, axis=1)
    p2 = OUT / "font_dark_4x.png"
    Image.fromarray(big2).save(p2)
    print(f"  → {p2.name} ({big2.shape[1]}×{big2.shape[0]})")

    # ── ④ 也扫大片区域，看还有没有别的字库 ───────────────────────
    print("\n" + "=" * 78)
    print("④ 扫整个 VRAM：每个 0x2000 区块的字形密度")
    print("=" * 78)
    for base in range(0, len(vram), 0x2000):
        seg_tiles = list(range(base // 32, min(base // 32 + 256, total_tiles)))
        n_glyph = sum(1 for t in seg_tiles
                      if set(tile_nibbles(vram, t).flatten().tolist()) & {11, 12})
        print(f"  0x{base:05X}..0x{base+0x2000:05X}: "
              f"{n_glyph:>3}/256 个 tile 含灰阶"
              f"{'  ★ 有字形' if n_glyph > 20 else ''}")

    # ── ⑤ 打印前 3 行汉字的 ASCII，确认可读 ─────────────────────
    print("\n" + "=" * 78)
    print("⑤ 前 3 行汉字的 ASCII（每行 12 字，用 2=深灰 1=浅灰 显示）")
    print("=" * 78)
    for rowpair in range(3):
        t0 = rowpair * 48          # 每行汉字 = 2 行 tile = 48 tiles
        print(f"\n  --- 汉字行 {rowpair + 1} ---")
        for y in range(16):        # 16 像素高
            line = ""
            for col in range(24):
                t = t0 + (y // 8) * 24 + col
                m = tile_nibbles(vram, t)
                yy = y % 8
                for x in range(8):
                    v = m[yy, x]
                    if v == 12:
                        line += "█"
                    elif v == 11:
                        line += "▒"
                    else:
                        line += " "
            print(f"    |{line}|")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
