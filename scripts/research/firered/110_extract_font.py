#!/usr/bin/env python3
"""调研(110) 抓完整字库 —— 0x08FE4660 就是字库数据源。

═══════════════════════════════════════════════════════════════════════════
【证据链完整了】
═══════════════════════════════════════════════════════════════════════════
 反汇编 0x08FE4814（汉化新增代码）：
     8fe4816: ldr  r5,[pc,#92]   → 0x06010000  （OBJ VRAM 基址）
     8fe481a: ldr  r0,[pc,#84]   → **0x08FE4660**  （字库数据源！）
     8fe481c: ldr  r3,[pc,#88]   → 0x08FE4860  （目标偏移表）
     8fe481e: ldr  r1,[r3,#0]    → 偏移 0x2C0
     8fe4820: adds r1,r1,r5      → 目标 = 0x060102C0
     8fe4822: movs r2,#8         → 8 个 u32 = **32 字节 = 一个 4bpp tile**
     8fe4824: bl   0x08FE4852    → 拷贝循环（ldr/str 各 32 字节）
     8fe4828: adds r0,#32        → 源 +32
     8fe482a: ldr  r1,[r3,#4]    → 偏移 0x2E0
     ... 重复 4 次（4 个 tile = 一个汉字的上/下/左/右）

 实测数据：
     0x08FE4660: 22 22 22 22 ... 11 ... 12 11 ...
                 其中 0x22 = nibble(2,2)、0x11 = (1,1)、0x12 = (1,2)
     原版该位置：ff ff ff ff ...（全空）

 ⇒ **0x08FE4660 就是汉化新增的字库数据**，格式 = 4bpp，每 tile 32 字节。
    与 VRAM 里看到的 nibble 10/11/12 不同 —— 在 ROM 里是 1/2，
    上屏时通过 palette 映射成浅灰/深灰。

【本脚本】
 ① 确认字库的起止范围（往后扫，找连续的 4bpp tile 数据）
 ② 数出总字数
 ③ 全部导出成字库大图
 ④ 与 (94) 已知的字交叉验证

用法：python scripts/research/firered/110_extract_font.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
FONT = 0xFE4660


def nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            b = blob[y * 4 + x // 2]
            m[y, x] = (b & 0x0F) if x % 2 == 0 else (b >> 4)
    return m


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))

    print("=" * 78)
    print("① 字库起点 0x08FE4660 前后")
    print("=" * 78)
    for i in range(-2, 8):
        off = FONT + i * 32
        blob = zh[off:off + 32]
        u = sorted(set(k for b in blob for k in (b & 0xF, b >> 4)))
        old = ja[off:off + 32]
        same = "同原版" if blob == old else "★汉化新增"
        print(f"  tile[{i:>2}] @0x{BASE+off:08X}  nibble={u}  {same}")

    # ── ② 往后扫，找字库范围 ───────────────────────────────────
    print("\n" + "=" * 78)
    print("② 往后扫：字库到哪结束")
    print("=" * 78)
    off = FONT
    last_valid = off
    gap = 0
    while off + 32 <= n:
        blob = zh[off:off + 32]
        u = set(k for b in blob for k in (b & 0xF, b >> 4))
        # 有效字形：nibble 在 1~3 之间（字库用 1/2/3）
        valid = bool(u & {1, 2}) and u <= {0, 1, 2, 3, 15}
        if valid:
            last_valid = off
            gap = 0
        else:
            gap += 1
            if gap > 64:      # 连续 64 个无效 tile 就认为结束
                break
        off += 32
    total_tiles = (last_valid - FONT) // 32 + 1
    print(f"  字库范围 0x{BASE+FONT:08X} .. 0x{BASE+last_valid:08X}")
    print(f"  共 {total_tiles} 个 32B tile = **{total_tiles // 4} 个 4-tile 字形**")
    print(f"    或 {total_tiles // 2} 个 2-tile 字形")

    # ── ③ 导出字库图（每 4 个 tile 拼一个 16×16 字形）──────────
    print("\n" + "=" * 78)
    print("③ 导出字库（每 4 tile = 16×16 字形）")
    print("=" * 78)
    from PIL import Image

    n_glyph = total_tiles // 4
    COLS = 16
    ROWS = (n_glyph + COLS - 1) // COLS
    W, H = COLS * 16 + COLS * 2 + 2, ROWS * 16 + ROWS * 2 + 2
    canvas = np.full((H, W, 3), 240, dtype=np.uint8)

    for gi in range(n_glyph):
        # 4 个 tile 的顺序：先试 [0,1,2,3] = 左上/左下/右上/右下
        t0 = FONT + gi * 128
        quad = []
        for k in range(4):
            quad.append(nibs(zh[t0 + k * 32: t0 + (k + 1) * 32]))
        # 拼 16×16：tile0=左上, tile1=左下, tile2=右上, tile3=右下
        cell = np.zeros((16, 16), dtype=np.uint8)
        cell[0:8, 0:8] = quad[0]
        cell[8:16, 0:8] = quad[1]
        cell[0:8, 8:16] = quad[2]
        cell[8:16, 8:16] = quad[3]

        r, c = gi // COLS, gi % COLS
        y0 = 2 + r * 18
        x0 = 2 + c * 18
        for yy in range(16):
            for xx in range(16):
                v = cell[yy, xx]
                if v == 2:
                    canvas[y0 + yy, x0 + xx] = (0, 0, 0)
                elif v == 1:
                    canvas[y0 + yy, x0 + xx] = (160, 160, 160)
                elif v == 3:
                    canvas[y0 + yy, x0 + xx] = (200, 0, 0)

    big = np.repeat(np.repeat(canvas, 3, axis=0), 3, axis=1)
    p = ROOT / "work" / "_probe" / "glyphs" / "ROM_FONT_atlas.png"
    Image.fromarray(big).save(p)
    print(f"  → {p.name}  ({big.shape[1]}×{big.shape[0]})")
    print(f"    {n_glyph} 个字形，{ROWS} 行 × {COLS} 列")

    # ── ④ 打印前 12 个字形（另一种 tile 排列）───────────────────
    print("\n" + "=" * 78)
    print("④ 前 12 个字形（tile 顺序 [0,1,2,3] 上下左右）")
    print("=" * 78)
    for gi in range(12):
        t0 = FONT + gi * 128
        quad = [nibs(zh[t0 + k * 32: t0 + (k + 1) * 32]) for k in range(4)]
        cell = np.zeros((16, 16), dtype=np.uint8)
        cell[0:8, 0:8] = quad[0]
        cell[8:16, 0:8] = quad[1]
        cell[0:8, 8:16] = quad[2]
        cell[8:16, 8:16] = quad[3]
        print(f"\n  字形 {gi} @0x{BASE+t0:08X}:")
        for yy in range(16):
            print("    " + "".join(
                "#" if cell[yy, xx] == 2 else ("+" if cell[yy, xx] == 1 else ".")
                for xx in range(16)))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
