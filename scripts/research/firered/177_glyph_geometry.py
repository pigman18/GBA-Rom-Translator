#!/usr/bin/env python3
"""调研(177) 确认「一个字 = 几个 8x8 tile」，并还原 tilemap 上的实际字形。

═══════════════════════════════════════════════════════════════════════════
【(176) 发现的新事实】
═══════════════════════════════════════════════════════════════════════════
tilemap（0xF000）里 pal=15 的 tile 序号是 1..288 连续，但**有笔画的只有一部分**，
且呈 48 个一组的规律：1-7 / 25-31 / 49-56 / 73-80 / 97-106 / 121-130 ...

这说明 charBase 里是「48 tile 一个槽位块」的缓存结构，不是紧密排列的字库。

【本脚本要回答的三个问题】
 Q1 一个汉字占几个 tile？（1 / 2 / 4）
    → 方法：把 tilemap 每一行的相邻 tile 拼起来看字形是否连续。
 Q2 汉字在屏幕上是「一格一 tile」还是「一格跨两 tile」？
    → 方法：找 tilemap 里相邻两项 tile 序号是否连续（字内部拼接）
 Q3 半角字符（数字/英文）占几个 tile？
    → 已知 tile 49-56 那批带 nibble=1（墨少、底多）疑似半角

【核心方法：不猜，用「相邻关系」实证】
 如果汉字 = 2 tile 横向拼接，则 tilemap 里同一个字的两项 tile 序号必然连续，
 且第一项落在某字形的左半、第二项落在右半。
 如果汉字 = 1 tile，则每个 tile 自身就是完整 8x8 字。

用法：python scripts/research/firered/177_glyph_geometry.py
"""
from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
VRAM = 0x06000000
SCREEN_BASE = 0xF000


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def tile_nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0x0F) if x % 2 == 0 else (v >> 4)
    return m


def show(m: np.ndarray) -> list[str]:
    tbl = {0: ".", 10: " ", 11: "+", 12: "#", 13: "*", 14: "%", 15: "@"}
    return ["".join(tbl.get(int(v), "?") for v in row) for row in m]


def main() -> int:
    vr = (SNAP / "vram.bin").read_bytes()

    # ── Q1/Q2：看 tilemap 相邻项的 tile 序号关系 ────────────
    print("=" * 78)
    print("Q1 相邻 tile 序号差（判断字是否跨 tile 拼接）")
    print("=" * 78)
    diffs: Counter[int] = Counter()
    pairs: list[tuple[int, int, int, int]] = []  # r, c, t0, t1
    for r in range(20):
        prev = None
        for c in range(30):
            e = rd16(vr, SCREEN_BASE + (r * 32 + c) * 2)
            if ((e >> 12) & 0xF) != 15:
                prev = None
                continue
            t = e & 0x3FF
            if prev is not None:
                d = t - prev
                diffs[d] += 1
                pairs.append((r, c - 1, prev, t))
            prev = t
    print("  相邻文字 tile 的序号差分布：")
    for d, n in diffs.most_common(12):
        print(f"    t[i+1]-t[i] = {d:>4}  x{n}")

    # ── 关键：如果差=1，说明是同一字的两半 ─────────────────
    d1 = diffs.get(1, 0)
    total = sum(diffs.values())
    print(f"\n  差=1（疑似同字拼接）：{d1}/{total} = {d1 / total:.1%}")

    # ── 打印几组「差=1」的样例，肉眼看是否拼成完整汉字 ─────
    print("\n" + "=" * 78)
    print("Q2 差=1 的样例（把两个 tile 拼成 8x16 看像不像一个字）")
    print("=" * 78)
    shown = 0
    for r, c, t0, t1 in pairs:
        if r > 6 or shown >= 6:
            break
        if t1 - t0 != 1:
            continue
        o0, o1 = t0 * 32, t1 * 32
        if o1 + 32 > len(vr):
            continue
        m0 = tile_nibs(vr[o0:o0 + 32])
        m1 = tile_nibs(vr[o1:o1 + 32])
        comb = np.hstack([m0, m1])
        print(f"\n  行 {r} 列 {c}: tile {t0}+{t1} @0x{VRAM + o0:08X}")
        for line in show(comb):
            print(f"    {line}")
        shown += 1

    # ── Q3：把整行文字拼起来（按 tilemap 顺序，tile 各占 8px）──
    print("\n" + "=" * 78)
    print("Q3 整行还原（每个 tilemap 项画 8x8，看文字是否连贯）")
    print("=" * 78)
    text_rows = []
    for r in range(20):
        row_tiles = []
        for c in range(30):
            e = rd16(vr, SCREEN_BASE + (r * 32 + c) * 2)
            if ((e >> 12) & 0xF) != 15:
                row_tiles.append(None)
            else:
                row_tiles.append(e & 0x3FF)
        if any(t is not None for t in row_tiles):
            text_rows.append((r, row_tiles))
    print(f"  有文字的行：{[r for r, _ in text_rows]}")
    for r, row_tiles in text_rows[:6]:
        canvas = np.full((8, 30 * 8), 10, dtype=np.uint8)
        for c, t in enumerate(row_tiles):
            if t is None:
                continue
            off = t * 32
            if off + 32 > len(vr):
                continue
            canvas[:, c * 8:(c + 1) * 8] = tile_nibs(vr[off:off + 32])
        print(f"\n  行 {r}:")
        for y in range(8):
            print("    " + "".join(
                {0: ".", 10: " ", 11: "+", 12: "#"}.get(int(v), "?")
                for v in canvas[y]))

    # ── Q4：统计「有笔画的 tile」总数 ─────────────────────
    print("\n" + "=" * 78)
    print("Q4 VRAM charBase 里真正含笔画的 tile 数（pal15 区）")
    print("=" * 78)
    inked = []
    for t in range(0, 1024):
        off = t * 32
        if off + 32 > len(vr):
            break
        m = tile_nibs(vr[off:off + 32])
        n12 = int(np.sum(m == 12))
        n11 = int(np.sum(m == 11))
        if n12 + n11 > 0:
            inked.append(t)
    print(f"  含笔画的 tile：{len(inked)} 个")
    print(f"  序号：{inked[:40]}{' ...' if len(inked) > 40 else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
