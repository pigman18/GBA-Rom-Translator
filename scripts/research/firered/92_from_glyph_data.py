#!/usr/bin/env python3
"""调研(92) 从字形数据本身出发抓字库 —— 不再经过 tilemap。

═══════════════════════════════════════════════════════════════════════════
【为什么之前切得乱七八糟】
═══════════════════════════════════════════════════════════════════════════
(86)-(91) 都是「先渲染 tilemap 一整行，再按 13px 横切」。
但 tilemap 里**边框和文字混在一起**（pal=2 是边框、pal=15 是文字），
所以切出来每格都有边框的竖条/横线。

【换思路：直接按字形数据切】
(87) 已确认含灰阶（nibble 11/12）的 tile 有 135 个，聚成 14 段：
    tile 1..7, 25..31, 49..56, 73..80, 97..106, 121..130,
    145..153, 169..177, 193..200, 217..224, 241..249, 265..273
    （这些是字形）+ 433..441（边框）+ 1920..1951（tilemap）

注意规律：每段起点间隔 24（1→25→49→73→97→121→145→169→193→217→241→265）。
而每段内部 7~10 个连续 tile。

⇒ 若每段是**一行文字**，段内每个 tile 是一个字的**左侧 8px**，
   则该行 24 个 tile 里前 N 个是字、后面是空白。
   即：**一个汉字 = 1 个 tile**（8px 宽），不是 2 tile。

这与「11px 宽」矛盾，除非字是**跨 tile 拼接**（11 = 8 + 3）。

本脚本：
 ① 验证「一个汉字 = tile n 的 8px + tile n+1 的 3px」
 ② 按这个规则重建字形，导出字库
 ③ 与截图逐字比对验证

用法：python scripts/research/firered/92_from_glyph_data.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "glyphs"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def tnib(vram: bytes, t: int) -> np.ndarray:
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

    def is_ink(a):
        return (a == 11) | (a == 12) | (a == 1)

    print("=" * 78)
    print("① 逐段检查：段内每个 tile 的墨量")
    print("=" * 78)
    segments = [(1, 7), (25, 31), (49, 56), (73, 80), (97, 106),
                (121, 130), (145, 153), (169, 177), (193, 200),
                (217, 224), (241, 249), (265, 273)]
    for a, b in segments:
        inks = []
        for t in range(a, b + 1):
            m = tnib(vram, t)
            inks.append(int(is_ink(m).sum()))
        print(f"  tile {a:>3}..{b:<3}: 墨量 {inks}")

    print("\n" + "=" * 78)
    print("② 关键验证：段内 tile 是不是「一个汉字的上半」")
    print("=" * 78)
    # 若 tile n 是上半、n+24 是下半，那么 n 与 n+24 的墨量应该相关
    a0 = 1
    up = tnib(vram, a0)
    dn = tnib(vram, a0 + 24)
    print(f"  tile {a0}（上半）与 tile {a0+24}（下半）：")
    print("    上半:")
    for y in range(8):
        print("      " + "".join("██" if v == 12 else ("▒▒" if v == 11
              else "  ") for v in up[y]))
    print("    下半:")
    for y in range(8):
        print("      " + "".join("██" if v == 12 else ("▒▒" if v == 11
              else "  ") for v in dn[y]))

    # ── ③ 拼成 16×8 看是不是一个字 ────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 上下拼成 16×8，看是不是完整汉字")
    print("=" * 78)
    for t in (1, 2, 3):
        combo = np.vstack([tnib(vram, t), tnib(vram, t + 24)])
        print(f"\n  tile {t} + {t+24} 拼成 16×8：")
        for y in range(16):
            print("    " + "".join("██" if v == 12 else ("▒▒" if v == 11
                  else "  ") for v in combo[y]))

    # ── ④ 也试「左右拼」：tile n + n+1 ───────────────────────────
    print("\n" + "=" * 78)
    print("④ 左右拼（tile n + n+1）8×16")
    print("=" * 78)
    for t in (1, 3, 5):
        combo = np.hstack([tnib(vram, t), tnib(vram, t + 1)])
        print(f"\n  tile {t} + {t+1} 拼成 8×16：")
        for y in range(8):
            print("    " + "".join("██" if v == 12 else ("▒▒" if v == 11
                  else "  ") for v in combo[y]))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
