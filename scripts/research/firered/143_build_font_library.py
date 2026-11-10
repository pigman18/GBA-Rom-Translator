#!/usr/bin/env python3
"""调研(143) 提取完整字库：0x083Cxxxx 的 50 个 LZ77 块解压后拼成字库。

═══════════════════════════════════════════════════════════════════════════
【(142) 的突破】
═══════════════════════════════════════════════════════════════════════════
0x083C0000 区成功解压 **50 个 LZ77 块**，合计 **208,384 字节**。
按每字 128 B 算 = **1628 个字**（接近所需的 2200）。

关键：这些块是 **GBA 标准 LZ77（0x10 头）**，
(119) 之所以漏掉，是因为判据「解压后必须同时含 nibble 1 和 2」太严——
抗锯齿字形有些块只有 1、有些只有 2。

【本脚本】
 ① 把 0x083C0000..0x083F0000 全部 LZ77 块解压
 ② 记录每块的 (地址, 解压数据)，按地址排序
 ③ 全部拼接，按 128 B/字切成字形
 ④ 用 palette 映射（1=浅灰 2=深灰）导出字库 PNG
 ⑤ 统计：多少字、多少个非空

用法：python scripts/research/firered/143_build_font_library.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
OUT = ROOT / "work" / "_probe" / "fontlib"


def lz77_decompress(data: bytes):
    if len(data) < 4 or (data[0] >> 4) != 1:
        return None
    size = ((data[0] & 0xF) << 24) | (data[1] << 16) | \
           (data[2] << 8) | data[3]
    if size == 0 or size > 0x100000:
        return None
    out = bytearray()
    i = 4
    while len(out) < size:
        if i >= len(data):
            return None
        flags = data[i]
        i += 1
        for bit in range(7, -1, -1):
            if len(out) >= size:
                break
            if i >= len(data):
                return None
            if not (flags >> bit) & 1:
                out.append(data[i])
                i += 1
            else:
                if i + 1 >= len(data):
                    return None
                b0, b1 = data[i], data[i + 1]
                i += 2
                disp = ((b0 & 0xF) << 8) | b1
                ln = (b0 >> 4) + 3
                if disp == 0 or disp > len(out):
                    return None
                for _ in range(ln):
                    if len(out) >= size:
                        break
                    out.append(out[-disp])
    return bytes(out)


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()

    print("=" * 78)
    print("① 解压 0x083C0000..0x083F0000 所有 LZ77 块")
    print("=" * 78)
    blocks = []
    off = 0x3C0000
    while off < 0x3F0000:
        if (zh[off] >> 4) == 1:
            size = ((zh[off] & 0xF) << 24) | (zh[off + 1] << 16) | \
                   (zh[off + 2] << 8) | zh[off + 3]
            if 256 <= size <= 0x100000:
                out = lz77_decompress(zh[off:off + size * 2 + 128])
                if out is not None and len(out) == size:
                    blocks.append((off, size, out))
        off += 4

    total = sum(b[1] for b in blocks)
    print(f"  {len(blocks)} 个块，合计 {total:,} 字节")

    # ── ② 全部拼接 ────────────────────────────────────────
    allbytes = b"".join(b[2] for b in blocks)

    # ── ③ 按 128 B 切成字形（4 tile = 16×16）──────────────
    print("\n" + "=" * 78)
    print("② 按 128 B/字切")
    print("=" * 78)
    n_glyph = len(allbytes) // 128
    print(f"  {n_glyph} 个字位")

    # 统计每个字位的墨量
    def glyph_maps(blob: bytes):
        """128 B → 4 个 8×8 tile。"""
        tiles = []
        for k in range(4):
            tb = blob[k * 32:(k + 1) * 32]
            m = np.zeros((8, 8), dtype=np.uint8)
            for y in range(8):
                for x in range(8):
                    b = tb[y * 4 + x // 2]
                    m[y, x] = (b & 0xF) if x % 2 == 0 else (b >> 4)
            tiles.append(m)
        return tiles

    inks = []
    for g in range(n_glyph):
        blob = allbytes[g * 128:(g + 1) * 128]
        tiles = glyph_maps(blob)
        ink = sum(int((t > 0).sum()) for t in tiles)
        inks.append(ink)

    inks = np.array(inks)
    print(f"  墨量：均值 {inks.mean():.1f} 中位 {np.median(inks):.0f} "
          f"最大 {inks.max()}")
    print(f"  非空（墨量>8）：{int((inks > 8).sum())}")
    print(f"  空白（墨量≤8）：{int((inks <= 8).sum())}")

    # ── ④ 画前 20 个字位 ──────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 前 16 个字位")
    print("=" * 78)
    shown = 0
    for g in range(n_glyph):
        if inks[g] <= 8:
            continue
        blob = allbytes[g * 128:(g + 1) * 128]
        tiles = glyph_maps(blob)
        # 拼 16×16：tile0=左上 tile1=左下 tile2=右上 tile3=右下
        cell = np.zeros((16, 16), dtype=np.uint8)
        cell[0:8, 0:8] = tiles[0]
        cell[8:16, 0:8] = tiles[1]
        cell[0:8, 8:16] = tiles[2]
        cell[8:16, 8:16] = tiles[3]
        print(f"\n  字位 {g}（墨量 {inks[g]}）：")
        for yy in range(16):
            print("    " + "".join(
                "#" if cell[yy, xx] == 2 else
                ("+" if cell[yy, xx] == 1 else
                 ("o" if cell[yy, xx] == 3 else "."))
                for xx in range(16)))
        shown += 1
        if shown >= 16:
            break

    # ── ⑤ 导出 PNG 字库 ───────────────────────────────────
    print("\n" + "=" * 78)
    print("④ 导出字库 PNG")
    print("=" * 78)
    try:
        from PIL import Image
        COLS = 16
        ROWS = (n_glyph + COLS - 1) // COLS
        CW = CH = 16
        GAP = 2
        W = COLS * (CW + GAP) + GAP
        H = ROWS * (CH + GAP) + GAP
        canvas = np.full((H, W, 3), 240, dtype=np.uint8)

        for g in range(n_glyph):
            blob = allbytes[g * 128:(g + 1) * 128]
            tiles = glyph_maps(blob)
            cell = np.zeros((16, 16), dtype=np.uint8)
            cell[0:8, 0:8] = tiles[0]
            cell[8:16, 0:8] = tiles[1]
            cell[0:8, 8:16] = tiles[2]
            cell[8:16, 8:16] = tiles[3]
            r, c = g // COLS, g % COLS
            y0 = GAP + r * (CH + GAP)
            x0 = GAP + c * (CW + GAP)
            for yy in range(16):
                for xx in range(16):
                    v = cell[yy, xx]
                    if v == 2:
                        canvas[y0 + yy, x0 + xx] = (0, 0, 0)
                    elif v == 1:
                        canvas[y0 + yy, x0 + xx] = (150, 150, 150)
                    elif v == 3:
                        canvas[y0 + yy, x0 + xx] = (200, 0, 0)

        big = np.repeat(np.repeat(canvas, 3, axis=0), 3, axis=1)
        p = OUT / "FONT_LIBRARY.png"
        Image.fromarray(big).save(p)
        print(f"  → {p.name}  ({big.shape[1]}×{big.shape[0]})")
        print(f"    {n_glyph} 字位，{ROWS} 行 × {COLS} 列")
    except ImportError:
        print("  没有 PIL")

    # 保存原始解压数据
    (OUT / "font_raw.bin").write_bytes(allbytes)
    print(f"  → font_raw.bin（{len(allbytes):,} 字节）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
