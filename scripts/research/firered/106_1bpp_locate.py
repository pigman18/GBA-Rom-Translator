#!/usr/bin/env python3
"""调研(106) 追 1bpp 线索：363/1197 命中，找它集中在哪。

═══════════════════════════════════════════════════════════════════════════
【为什么转 1bpp 命中率更高】
═══════════════════════════════════════════════════════════════════════════
(104) 三种格式的命中率：
   4bpp 原样          151 / 1197 (12.6%)  ← 分散在多处，像是巧合
   4bpp 去抗锯齿       69 / 1197 ( 5.8%)
   **1bpp（深灰=1）     363 / 1197 (30.3%)** ← 最高！

1bpp 每字只有 8 字节（8 行 × 1 字节），**误命中概率低**
（8 字节里 8 位都要对上），却命中 30%，这个信号很强。

⇒ 字库可能是 **1bpp 存储**，上屏时展开成 4bpp。

【本脚本】
 ① 用 1bpp 形式重新搜全部 1197 个字形
 ② 把命中位置按区聚簇，找**连续且等距**的字库
 ③ 验证该区：按 8 字节/tile 切，画出字，看是不是汉字
 ④ 统计字库总字数

用法：python scripts/research/firered/106_1bpp_locate.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
LOAD = ROOT / "work" / "_probe" / "glyphload"
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def to1bpp(blob: bytes) -> bytes:
    """4bpp nibble 图 → 1bpp（深灰 12 → 1，浅灰 11 → 1，其余 → 0）。"""
    out = bytearray()
    for y in range(8):
        row = 0
        for x in range(8):
            b = blob[y * 4 + x // 2]
            v = (b & 0xF) if x % 2 == 0 else (b >> 4)
            row = (row << 1) | (1 if v in (11, 12) else 0)
        out.append(row)
    return bytes(out)


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()

    # 收集字形
    glyphs = set()
    for tag in ("A_menu", "B_world", "C_start", "D_down", "E_back"):
        p = LOAD / f"{tag}.vram.bin"
        if not p.exists():
            continue
        v = p.read_bytes()
        for t in range(len(v) // 32):
            blob = v[t * 32:(t + 1) * 32]
            nib = set()
            for b in blob:
                nib.add(b & 0xF)
                nib.add(b >> 4)
            if nib & {11, 12}:
                glyphs.add(blob)

    print("=" * 78)
    print("① 用 1bpp 形式搜全部字形")
    print("=" * 78)
    hits = []
    for g in glyphs:
        b1 = to1bpp(g)
        if len(set(b1)) <= 1:
            continue
        i = zh.find(b1)
        while i >= 0:
            hits.append((i, b1))
            i = zh.find(b1, i + 1)
    print(f"  命中 {len(hits)} 处")

    c = Counter(h // 0x10000 for h, _ in hits)
    print(f"  按 64KB 分布：")
    for k, v in c.most_common(12):
        print(f"    0x{BASE+k*0x10000:08X}: {v} 处")

    # ── ② 找最密集区并检查等距性 ────────────────────────────────
    print("\n" + "=" * 78)
    print("② 最密集区里的命中是否等距（等距 = 字库）")
    print("=" * 78)
    if not c:
        return 0
    top = c.most_common(1)[0][0]
    lo = top * 0x10000
    sub = sorted(h for h, _ in hits if lo <= h < lo + 0x10000)
    print(f"  区 0x{BASE+lo:08X}：{len(sub)} 处")
    print(f"  范围 0x{BASE+min(sub):08X} .. 0x{BASE+max(sub):08X}")
    gaps = Counter(np.diff(sub).tolist())
    print(f"  相邻命中间隔 top8：{gaps.most_common(8)}")

    # ── ③ 把该区按 8 字节/tile 全画出来 ─────────────────────────
    print("\n" + "=" * 78)
    print("③ 该区按 8 字节切，画前 20 个")
    print("=" * 78)
    start = min(sub)
    start = start - (start % 8)
    for k in range(20):
        off = start + k * 8
        if off + 8 > len(zh):
            break
        blob = zh[off:off + 8]
        # 只有「1bpp 有效」的才画
        if len(set(blob)) <= 1:
            continue
        print(f"\n  tile {k} @0x{BASE+off:08X}  {blob.hex(' ')}")
        for y in range(8):
            print("    " + "".join(
                "#" if (blob[y] >> (7 - x)) & 1 else "."
                for x in range(8)))

    # ── ④ 原版对照 ──────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("④ 原版同区")
    print("=" * 78)
    seg = ja[start:start + 0x400]
    print(f"  原版 0x{BASE+start:08X} 起 0x400：非 FF "
          f"{sum(1 for b in seg if b != 0xFF)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
