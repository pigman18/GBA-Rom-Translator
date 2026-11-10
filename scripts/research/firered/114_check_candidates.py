#!/usr/bin/env python3
"""调研(114) 看两个汉化新增的字形候选区：0x089B2B60 与 0x08AB72E0。

═══════════════════════════════════════════════════════════════════════════
【(113) 结果】
═══════════════════════════════════════════════════════════════════════════
满足「nibble ≤3 的连续块」且**原版全 FF**（汉化完全新增）的只有两处：
    0x089B2B60   509 块  16,288 字节
    0x08AB72E0   265 块   8,480 字节

其余 run 的原版非 FF = 块数，说明原版就有（可能是原版字库/图形）。

 509 块 × 32 B = 16288 B。若每字 4 tile（128 B）→ 127 个字
 若每字 2 tile（64 B）→ 254 个字
 若每字 1 tile（32 B）→ 509 个字  ← 最接近「一页字库」

【本脚本】
 ① 画这两个区，试 1/2/4 块拼法
 ② 判断哪个能画出汉字
 ③ 与 (94) 已确认的字（继续游戏/主角/时间…）比对

用法：python scripts/research/firered/114_check_candidates.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
CAND = [(0x9B2B60, 509), (0xAB72E0, 265)]


def nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            b = blob[y * 4 + x // 2]
            m[y, x] = (b & 0x0F) if x % 2 == 0 else (b >> 4)
    return m


def show(m: np.ndarray, w: int = 8) -> None:
    for y in range(m.shape[0]):
        print("      " + "".join(
            "." if m[y, x] == 0 else str(m[y, x]) for x in range(m.shape[1])))


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()

    for start, cnt in CAND:
        print("=" * 78)
        print(f"区 0x{BASE+start:08X}（{cnt} 块）")
        print("=" * 78)
        # 确认原版
        seg_j = ja[start:start + cnt * 32]
        nz = sum(1 for b in seg_j if b != 0xFF)
        print(f"  原版非 FF：{nz}  ⇒ {'汉化完全新增' if nz == 0 else '原版有数据'}")

        # nibble 分布
        from collections import Counter
        c = Counter()
        for k in range(min(cnt, 200)):
            blob = zh[start + k * 32: start + (k + 1) * 32]
            for b in blob:
                c[b & 0xF] += 1
                c[b >> 4] += 1
        print(f"  nibble 分布：{dict(sorted(c.items()))}")

        # 画前 6 块
        print(f"\n  前 6 块：")
        for k in range(6):
            blob = zh[start + k * 32: start + (k + 1) * 32]
            print(f"\n    块{k}: {blob[:16].hex(' ')}")
            show(nibs(blob))

        # 试「2 块上下拼」「4 块 16×16」
        print(f"\n  试 4 块拼 16×16（左上/左下/右上/右下）：")
        for gi in range(3):
            cells = [nibs(zh[start + (gi * 4 + k) * 32:
                              start + (gi * 4 + k + 1) * 32])
                     for k in range(4)]
            cell = np.zeros((16, 16), dtype=np.uint8)
            cell[0:8, 0:8] = cells[0]
            cell[8:16, 0:8] = cells[1]
            cell[0:8, 8:16] = cells[2]
            cell[8:16, 8:16] = cells[3]
            print(f"\n    字形{gi}:")
            show(cell, 16)

        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
