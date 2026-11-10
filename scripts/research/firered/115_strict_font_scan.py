#!/usr/bin/env python3
"""调研(115) 收紧判据：字形块必须同时含 nibble 1 和 2。

═══════════════════════════════════════════════════════════════════════════
【(113)(114) 的教训】
═══════════════════════════════════════════════════════════════════════════
「nibble ≤ 3」这个判据把 **全 0 块**也当成字形块了。
0x089B2B60 那 509 块全是 00 —— 那是**清零**，不是字库。

【收紧后的判据】
 一个真正的字形块（8×8 汉字局部）必然：
  · nibble 值 ⊆ {0, 1, 2}（0=底、1=抗锯齿、2=笔画）
  · **同时含 1 和 2**（有笔画且有抗锯齿）
  · 墨量（nibble≥1 的像素数）在 4~56 之间（不能太空也不能全满）

满足这三条的块才是字形。再找连续 run。

用法：python scripts/research/firered/115_strict_font_scan.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def is_glyph_block(blob: bytes) -> tuple[bool, int, int]:
    """返回 (是否字形块, nibble1 数, nibble2 数)。"""
    n1 = n2 = 0
    other = 0
    for b in blob:
        for v in (b & 0xF, b >> 4):
            if v == 0:
                continue
            elif v == 1:
                n1 += 1
            elif v == 2:
                n2 += 1
            else:
                other += 1
    ink = n1 + n2
    ok = (other == 0) and (n1 > 0) and (n2 > 0) and (4 <= ink <= 56)
    return ok, n1, n2


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))
    nblk = n // 32

    print("=" * 78)
    print("① 严格判定每个 32B 块")
    print("=" * 78)
    ok_flags = np.zeros(nblk, dtype=bool)
    stats = []
    for k in range(nblk):
        blob = zh[k * 32:(k + 1) * 32]
        if len(blob) < 32:
            break
        ok, n1, n2 = is_glyph_block(blob)
        ok_flags[k] = ok
        if ok:
            stats.append((k * 32, n1, n2))
    print(f"  严格字形块：{len(stats):,} / {nblk:,}")

    # ── ② 找连续 run ────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 连续 run（≥32 块）")
    print("=" * 78)
    runs = []
    i = 0
    while i < nblk:
        if ok_flags[i]:
            j = i
            while j + 1 < nblk and ok_flags[j + 1]:
                j += 1
            if j - i + 1 >= 32:
                runs.append((i, j - i + 1))
            i = j + 1
        else:
            i += 1
    runs.sort(key=lambda r: -r[1])
    print(f"  找到 {len(runs)} 个 run")
    print(f"  {'起始':>14} {'块数':>6} {'字节':>8} {'原版非FF':>9} {'汉化新增?':>9}")
    for sb, cnt in runs[:20]:
        off = sb * 32
        seg_j = ja[off:off + cnt * 32]
        nz = sum(1 for b in seg_j if b != 0xFF)
        print(f"  0x{BASE+off:08X} {cnt:>6} {cnt*32:>8,} {nz:>9} "
              f"{'★是' if nz == 0 else '否':>9}")

    # ── ③ 画汉化新增的 run ─────────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 画「汉化完全新增」的 run")
    print("=" * 78)
    drawn = 0
    for sb, cnt in runs:
        off = sb * 32
        seg_j = ja[off:off + cnt * 32]
        if sum(1 for b in seg_j if b != 0xFF) > 0:
            continue
        print(f"\n  ==== 0x{BASE+off:08X}（{cnt} 块）====")
        for k in range(6):
            blob = zh[off + k * 32: off + (k + 1) * 32]
            ok, n1, n2 = is_glyph_block(blob)
            print(f"\n    块{k} n1={n1} n2={n2}")
            for y in range(8):
                row = blob[y * 4:(y + 1) * 4]
                line = ""
                for x in range(8):
                    b = row[x // 2]
                    v = (b & 0xF) if x % 2 == 0 else (b >> 4)
                    line += "." if v == 0 else ("+" if v == 1 else "#")
                print("      " + line)
        drawn += 1
        if drawn >= 3:
            break

    if drawn == 0:
        print("  没有「汉化完全新增 + 严格字形」的 run")
        print("  ⇒ 说明字库不是这种格式，或与其它数据混排")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
