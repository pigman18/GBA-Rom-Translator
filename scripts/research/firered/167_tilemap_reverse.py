#!/usr/bin/env python3
"""调研(167) 用 VRAM tilemap 反推：EWRAM 块最终落在屏幕哪个位置。

═══════════════════════════════════════════════════════════════════════════
【思路：用已知的 tilemap 反推块的语义】
═══════════════════════════════════════════════════════════════════════════
已知（(76)(83) 验证过）：
 · 菜单画面 BG1 的 tilemap 在 VRAM 0xF000（screenBase=0xF000，4bpp）
 · tilemap 每项：tile 序号（10 位）+ pal 字段（bit12-15）
 · 文字用 pal=15
 · 已成功还原整个画面（compare.png 上下一致）

⇒ 所以 tilemap 是**可靠的地面真相**。

本脚本：
 ① 从快照的 vram.bin 读 0xF000 的 tilemap
 ② 找出所有 pal=15 的文字 tile 序号
 ③ 按 tile 序号从 vram.bin 取出对应字形，横排拼成「屏幕上那一行字」
 ④ 同时：在 ewram.bin 里找「内容与这些 tile 完全相同」的块
    → 那些 EWRAM 块就是「还没送进 VRAM 的字形副本」
 ⑤ 从而确认：字形是先到 EWRAM 再去 VRAM 的

用法：python scripts/research/firered/167_tilemap_reverse.py
"""
from __future__ import annotations

import struct
from collections import Counter
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
    return {0: ".", 10: " ", 11: "+", 12: "#"}.get(v, str(v))


def main() -> int:
    vr = (SNAP / "vram.bin").read_bytes()
    ew = (SNAP / "ewram.bin").read_bytes()
    SB = 0xF000

    print("=" * 78)
    print("① tilemap（0xF000）里各 pal 的统计")
    print("=" * 78)
    pals = Counter()
    text_tiles = []
    for r in range(20):
        for c in range(30):
            e = rd16(vr, SB + (r * 32 + c) * 2)
            p = (e >> 12) & 0xF
            pals[p] += 1
            if p == 15:
                text_tiles.append((r, c, e & 0x3FF))
    print(f"  pal 分布：{dict(pals)}")
    print(f"  pal=15 的项：{len(text_tiles)}")

    # ── ② 按行渲染文字 ─────────────────────────────
    print("\n" + "=" * 78)
    print("② 按 tilemap 行渲染文字（pal=15）")
    print("=" * 78)
    rows_with_text = sorted({r for r, c, t in text_tiles})
    for r in rows_with_text[:8]:
        print(f"\n  行 {r}:")
        for y in range(8):
            line = ""
            for c in range(30):
                e = rd16(vr, SB + (r * 32 + c) * 2)
                if ((e >> 12) & 0xF) != 15:
                    line += " "
                    continue
                tidx = e & 0x3FF
                off = tidx * 32
                if off + 32 > len(vr):
                    line += "?"
                    continue
                m = nibs(vr[off:off + 32])
                line += ch(m[y, 3])   # 取中间列做概览
            print(f"    |{line}|")

    # ── ③ 精确渲染前 2 行（取每列像素）──────────────
    print("\n" + "=" * 78)
    print("③ 精确渲染（每 tile 8px 全画）")
    print("=" * 78)
    for r in rows_with_text[:3]:
        n_col = 30
        canvas = np.full((8, n_col * 8), 10, dtype=np.uint8)
        for c in range(n_col):
            e = rd16(vr, SB + (r * 32 + c) * 2)
            if ((e >> 12) & 0xF) != 15:
                continue
            tidx = e & 0x3FF
            off = tidx * 32
            if off + 32 > len(vr):
                continue
            canvas[:, c * 8:(c + 1) * 8] = nibs(vr[off:off + 32])
        print(f"\n  行 {r}:")
        for y in range(8):
            print("    " + "".join(ch(canvas[y, x]) for x in range(n_col * 8)))

    # ── ④ 在 EWRAM 里找与这些 tile 相同的块 ────────
    print("\n" + "=" * 78)
    print("④ EWRAM 里是否存有与 VRAM 文字 tile 相同的内容")
    print("=" * 78)
    vram_tiles = {}
    for r, c, tidx in text_tiles:
        off = tidx * 32
        if off + 32 <= len(vr):
            vram_tiles[tidx] = vr[off:off + 32]
    uniq_vram = set(vram_tiles.values())
    print(f"  VRAM 文字 tile：{len(vram_tiles)} 个，内容去重 {len(uniq_vram)}")

    # 在 EWRAM 里按 32B 找
    found = []
    for off in range(0, len(ew) - 32, 4):
        blob = ew[off:off + 32]
        if blob in uniq_vram:
            found.append(off)
    print(f"  EWRAM 里找到相同内容：{len(found)} 处")
    for o in found[:20]:
        print(f"    0x{0x02000000+o:08X}")

    # ── ⑤ 也看 EWRAM 里 nibble 10/11/12 的块与 VRAM 的关系 ─
    print("\n" + "=" * 78)
    print("⑤ EWRAM 的 10/11/12 块 vs VRAM 文字 tile")
    print("=" * 78)
    ew_glyph = []
    for off in range(0, len(ew) - 32, 32):
        blob = ew[off:off + 32]
        u = set(v for b in blob for v in (b & 0xF, b >> 4))
        if u <= {0, 10, 11, 12} and (11 in u or 12 in u):
            ew_glyph.append((off, blob))
    print(f"  EWRAM 字形候选块：{len(ew_glyph)}")
    same = sum(1 for _, b in ew_glyph if b in uniq_vram)
    print(f"  其中内容与 VRAM 文字 tile 相同的：{same}")

    if ew_glyph:
        print(f"\n  抽样 3 个 EWRAM 块 vs VRAM 里最像的 tile：")
        for off, blob in ew_glyph[:3]:
            print(f"\n    EWRAM 0x{0x02000000+off:08X}: {blob[:16].hex(' ')}")
            m = nibs(blob)
            for y in range(8):
                print("      " + "".join(ch(m[y, x]) for x in range(8)))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
