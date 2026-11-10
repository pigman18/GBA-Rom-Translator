#!/usr/bin/env python3
"""调研(117) 账本：汉化新增的 648KB 具体花在哪了。

═══════════════════════════════════════════════════════════════════════════
【已知总量】
═══════════════════════════════════════════════════════════════════════════
汉化相对原版新增字节：**648,523**
  · 主文本区 0x6D0000..0x722000（F7 中文）：约 344,064 字节（53%）
  · 剩下约 **304KB** 是别的 —— 字库应该在里面

【本脚本：把这 304KB 按 16KB 分块列清，每块判性质】
 判据：
  · F7 占比高 → 文本
  · nibble 只含 0/1/2 且含 1 和 2 → 字形
  · 其它 → 代码/表/未知

用法：python scripts/research/firered/117_bytes_ledger.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
TEXT = [(0x6D0000, 0x722000), (0xAF5000, 0xAFB000)]


def in_text(off: int) -> bool:
    return any(lo <= off < hi for lo, hi in TEXT)


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))

    print("=" * 78)
    print("① 汉化新增字节按 16KB 分块")
    print("=" * 78)
    SEG = 0x4000
    rows = []
    for base in range(0, n, SEG):
        a = ja[base:base + SEG]
        b = zh[base:base + SEG]
        if len(a) < SEG:
            break
        # 新增字节数（原版 FF、汉化非 FF）
        added = int(np.sum((np.frombuffer(a, dtype=np.uint8) == 0xFF) &
                           (np.frombuffer(b, dtype=np.uint8) != 0xFF)))
        if added < SEG * 0.05:
            continue
        seg = np.frombuffer(b, dtype=np.uint8)
        f7 = int((seg == 0xF7).sum())
        # nibble 统计
        hi = seg >> 4
        lo = seg & 0x0F
        n1 = int(((hi == 1) | (lo == 1)).sum())
        n2 = int(((hi == 2) | (lo == 2)).sum())
        bad = int(((hi > 3) | (lo > 3)).sum())
        is_text = in_text(base) or f7 > SEG * 0.05
        is_glyph = (bad < SEG * 0.02) and n1 > 50 and n2 > 50
        kind = ("文本" if is_text else
                "★字形?" if is_glyph else "其他")
        rows.append((base, added, f7, n1, n2, kind))

    print(f"  {'区':>14} {'新增':>7} {'F7':>6} {'nib1':>6} {'nib2':>6} 性质")
    for base, added, f7, n1, n2, kind in rows:
        print(f"  0x{BASE+base:08X} {added:>7} {f7:>6} {n1:>6} {n2:>6} {kind}")

    # ── ② 汇总 ────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 汇总")
    print("=" * 78)
    tot = sum(r[1] for r in rows)
    print(f"  有新增的 16KB 块：{len(rows)}，新增合计 {tot:,} 字节")

    glyph_rows = [r for r in rows if r[5] == "★字形?"]
    print(f"\n  「字形特征」块：{len(glyph_rows)} 个")
    gtot = 0
    for base, added, f7, n1, n2, kind in glyph_rows[:20]:
        print(f"    0x{BASE+base:08X}  新增 {added:>6}  nib1={n1} nib2={n2}")
        gtot += added
    if glyph_rows:
        print(f"    合计 {gtot:,} 字节")
        for per in (128, 64, 32):
            print(f"      按每字 {per} B → {gtot//per} 个字")

    text_rows = [r for r in rows if r[5] == "文本"]
    print(f"\n  「文本」块：{len(text_rows)}，合计 "
          f"{sum(r[1] for r in text_rows):,} 字节")

    other_rows = [r for r in rows if r[5] == "其他"]
    print(f"  「其他」块：{len(other_rows)}，合计 "
          f"{sum(r[1] for r in other_rows):,} 字节")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
