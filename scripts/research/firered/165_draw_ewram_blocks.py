#!/usr/bin/env python3
"""调研(165) 画出 EWRAM 里 216 个字形块 —— 直接看它们是不是汉字。

═══════════════════════════════════════════════════════════════════════════
【(164) 的结果】
═══════════════════════════════════════════════════════════════════════════
 nibble 分布：
    VRAM   : 10 → 8%   12 → 1%   11 → **0%**   （只有两档：白 + 深灰）
    EWRAM  : 10 → 3%   12 → 1%   1 → 1%
    IWRAM  : 分布更杂

 EWRAM 里「nibble ⊆ {0,10,11,12} 且含 11 或 12」的 32B 块：**216 个**
 聚成 15 段，最大两段：
     0x02002C40..0x02003240   48 块
     0x02000E40..0x02001420   47 块

 ⇒ **这 15 段很可能就是字形缓冲。** 48 块 × 32B = 1536B ≈ 12 个 4-tile 字形

 用「原始 1/2/3」判据找到的 63 块，24 个在 ROM 命中（都是原版相同，即原版图标）。
 用「10/11/12」判据的 36 块，ROM 命中 0 —— 这些是**运行时生成的**。

【本脚本：直接画】
 ① 把 15 段全部画成 ASCII
 ② 人眼判断是不是汉字
 ③ 若是，量字宽/步进

用法：python scripts/research/firered/165_draw_ewram_blocks.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"


def nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            b = blob[y * 4 + x // 2]
            m[y, x] = (b & 0x0F) if x % 2 == 0 else (b >> 4)
    return m


def ch(v: int) -> str:
    if v == 0:
        return "."
    if v == 10:
        return " "      # 白
    if v == 12:
        return "#"      # 深灰
    if v == 11:
        return "+"      # 浅灰
    return str(v)       # 其他


def main() -> int:
    ew = (SNAP / "ewram.bin").read_bytes()

    # 收集 10/11/12 的块
    blocks = []
    for off in range(0, len(ew) - 32, 32):
        blob = ew[off:off + 32]
        u = set(v for b in blob for v in (b & 0xF, b >> 4))
        if u <= {0, 10, 11, 12} and (11 in u or 12 in u):
            blocks.append((off, blob))

    # 聚段
    runs = []
    if blocks:
        s = p = blocks[0][0]
        cur = [blocks[0]]
        for off, blob in blocks[1:]:
            if off == p + 32:
                p = off
                cur.append((off, blob))
            else:
                runs.append((s, cur))
                s = p = off
                cur = [(off, blob)]
        runs.append((s, cur))
    runs.sort(key=lambda r: -len(r[1]))

    print("=" * 78)
    print(f"共 {len(blocks)} 个块，聚成 {len(runs)} 段")
    print("=" * 78)
    for a, bl in runs[:8]:
        print(f"  0x{0x02000000+a:08X}  {len(bl)} 块")

    # ── 画最大 4 段 ────────────────────────────────────
    for idx, (start, bl) in enumerate(runs[:4]):
        print("\n" + "=" * 78)
        print(f"段 {idx}: 0x{0x02000000+start:08X}  {len(bl)} 块 "
              f"= {len(bl)*32} 字节")
        print("=" * 78)
        for k, (off, blob) in enumerate(bl[:12]):
            m = nibs(blob)
            u = sorted(set(m.flatten().tolist()))
            print(f"\n  块 {k} @0x{0x02000000+off:08X}  nibble={u}")
            for y in range(8):
                print("    " + "".join(ch(m[y, x]) for x in range(8)))

    # ── 试「2 块上下拼」和「4 块 16×16」────────────────
    print("\n" + "=" * 78)
    print("试拼接：最大段的连续 4 块 = 16×16")
    print("=" * 78)
    if runs:
        start, bl = runs[0]
        for g in range(min(3, len(bl) // 4)):
            cells = [nibs(bl[g * 4 + k][1]) for k in range(4)]
            cell = np.zeros((16, 16), dtype=np.uint8)
            cell[0:8, 0:8] = cells[0]
            cell[8:16, 0:8] = cells[1]
            cell[0:8, 8:16] = cells[2]
            cell[8:16, 8:16] = cells[3]
            print(f"\n  字形 {g}:")
            for y in range(16):
                print("    " + "".join(ch(cell[y, x]) for x in range(16)))

    # ── 也试 2 块上下（8×16）───────────────────────────
    print("\n" + "=" * 78)
    print("试「2 块上下」8×16")
    print("=" * 78)
    if runs:
        start, bl = runs[0]
        for g in range(min(4, len(bl) // 2)):
            a = nibs(bl[g * 2][1])
            b = nibs(bl[g * 2 + 1][1])
            print(f"\n  字形 {g}:")
            for y in range(8):
                print("    " + "".join(ch(a[y, x]) for x in range(8)))
            for y in range(8):
                print("    " + "".join(ch(b[y, x]) for x in range(8)))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
