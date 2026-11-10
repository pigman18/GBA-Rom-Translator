#!/usr/bin/env python3
"""调研(166) 弄清 EWRAM 字形块的排列方式：按行排还是按列排。

═══════════════════════════════════════════════════════════════════════════
【(165) 的观察】
═══════════════════════════════════════════════════════════════════════════
段 1（0x02002F40，9 块）：
   块0: 前 1 行有墨，后 7 行也有   → 看起来是「一个字的上半」
   块1: 8 行都有墨
   块2: 8 行都有墨
   ...
   每块最后一行都是空（nibble 10）

⇒ 每块是 8×8，最后一行空 = 行间距。

段 0（0x02002C40，9 块）：
   块0-2: 前 3 行空，后 5 行有墨
   块3-8: 大部分有墨

⇒ 两段的差别说明它们**装的不是同一批字的不同部分**，而是**不同大小的字**。

【关键：把段内 9 块当成「一行的 9 个 8×8 字块」横排】
 若 9 块 = 一行显示 9 个字符（每个 8px 宽），则拼出来是一行 72px 宽的文字。
 中文菜单里「继续游戏」是 4 个汉字，若每字 8px 太窄（需 11px）。

⇒ 更可能：**2 块拼一个汉字（左 8 + 右 3）**，即 8+3=11 宽。

【本脚本】
 ① 把最大几段按「横向拼成一行」渲染
 ② 也试「2 块拼一字」「3 块拼一字」
 ③ 输出整行 ASCII，人眼判断

用法：python scripts/research/firered/166_layout_test.py
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
        return " "
    if v == 12:
        return "#"
    if v == 11:
        return "+"
    return str(v)


def runs_of(ew: bytes, allowed: set) -> list[tuple[int, list[bytes]]]:
    blocks = []
    for off in range(0, len(ew) - 32, 32):
        blob = ew[off:off + 32]
        u = set(v for b in blob for v in (b & 0xF, b >> 4))
        if u <= allowed and (11 in u or 12 in u):
            blocks.append((off, blob))
    runs = []
    if not blocks:
        return runs
    s = p = blocks[0][0]
    cur = [blocks[0][1]]
    for off, blob in blocks[1:]:
        if off == p + 32:
            p = off
            cur.append(blob)
        else:
            runs.append((s, cur))
            s = p = off
            cur = [blob]
    runs.append((s, cur))
    runs.sort(key=lambda r: -len(r[1]))
    return runs


def main() -> int:
    ew = (SNAP / "ewram.bin").read_bytes()
    runs = runs_of(ew, {0, 10, 11, 12})

    print("=" * 78)
    print(f"共 {len(runs)} 段")
    for a, bl in runs[:8]:
        print(f"  0x{0x02000000+a:08X}  {len(bl)} 块")
    print()

    # ── A) 横向拼成一行 8×N ─────────────────────────────
    print("=" * 78)
    print("A) 段内所有块横向拼成一行（每块 8px 宽）")
    print("=" * 78)
    for idx, (start, bl) in enumerate(runs[:4]):
        n = len(bl)
        canvas = np.full((8, n * 8), 10, dtype=np.uint8)
        for k, blob in enumerate(bl):
            canvas[:, k * 8:(k + 1) * 8] = nibs(blob)
        print(f"\n  段{idx} 0x{0x02000000+start:08X}（{n} 块 = {n*8}px）:")
        for y in range(8):
            print("    " + "".join(ch(canvas[y, x]) for x in range(n * 8)))

    # ── B) 按 2 块拼一字（8+3=11 宽）────────────────────
    print("\n" + "=" * 78)
    print("B) 2 块拼一字：左块 8px + 右块的左 3px = 11px 宽")
    print("=" * 78)
    for idx, (start, bl) in enumerate(runs[:3]):
        n_pair = len(bl) // 2
        if n_pair == 0:
            continue
        print(f"\n  段{idx}（{len(bl)} 块 → {n_pair} 个字）:")
        for g in range(min(n_pair, 6)):
            left = nibs(bl[g * 2])
            right = nibs(bl[g * 2 + 1])
            cell = np.full((8, 11), 10, dtype=np.uint8)
            cell[:, 0:8] = left
            cell[:, 8:11] = right[:, 0:3]
            print(f"\n    字{g}:")
            for y in range(8):
                print("      " + "".join(ch(cell[y, x]) for x in range(11)))

    # ── C) 纵向堆叠（把 bl 当成竖排）────────────────────
    print("\n" + "=" * 78)
    print("C) 纵向堆叠成 8×(8N)")
    print("=" * 78)
    for idx, (start, bl) in enumerate(runs[:2]):
        n = len(bl)
        canvas = np.full((n * 8, 8), 10, dtype=np.uint8)
        for k, blob in enumerate(bl):
            canvas[k * 8:(k + 1) * 8, :] = nibs(blob)
        print(f"\n  段{idx}（{n} 块竖排）:")
        for y in range(n * 8):
            print("    " + "".join(ch(canvas[y, x]) for x in range(8)))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
