#!/usr/bin/env python3
"""调研(113) 用「字形 nibble 特征」全 ROM 扫字库 —— 这次判据是对的。

═══════════════════════════════════════════════════════════════════════════
【已验证的字形特征（来自 (110)-(112) 实测）】
═══════════════════════════════════════════════════════════════════════════
 1. 汉化字库区 0x08FE4560 的字节：`22 21 21 22 11 11 11 21 22 22 22 22 12 11 11 22`
    ⇒ nibble 值只可能是 **0 / 1 / 2 / 3**（偶见 0）
 2. 原版该区全 FF ⇒ 是汉化新增
 3. 但该区只有 ~700 字节 = 装不下 2000 字
    ⇒ 它是**暂存区**，真正字库在别处

【本脚本：用 nibble 特征全 ROM 扫】
 判据（严格）：
   · 连续 N 个 32 字节块
   · 每块的 nibble 都在 {0,1,2,3} 里
   · 至少一半块含 1 或 2（不是全 0）
   · N ≥ 64（至少 16 个字形）

 这个判据很严格：普通代码/位图会有大量 nibble 4~15。

用法：python scripts/research/firered/113_scan_font_feature.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))

    # nibble 最大值表
    hi = np.frombuffer(zh[:n - n % 2], dtype=np.uint8)
    nib_hi = (hi >> 4)
    nib_lo = (hi & 0x0F)
    maxnib = np.maximum(nib_hi, nib_lo)

    print("=" * 78)
    print("① 逐 32 字节块判定「是否纯字形块」")
    print("=" * 78)
    # 块内所有字节的最大 nibble 都要 <= 3
    nblk = n // 32
    ok_block = np.zeros(nblk, dtype=bool)
    has12 = np.zeros(nblk, dtype=bool)
    for k in range(nblk):
        seg = maxnib[k * 32:(k + 1) * 32]
        if len(seg) < 32:
            break
        if seg.max() <= 3:
            ok_block[k] = True
            has12[k] = bool((nib_hi[k * 32:(k + 1) * 32] >= 1).any() or
                            (nib_lo[k * 32:(k + 1) * 32] >= 1).any())
    print(f"  纯字形块（nibble ≤3）：{int(ok_block.sum()):,} / {nblk:,}")

    # ── ② 找连续 run ────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 连续 run（≥64 块 = 16 个字形）")
    print("=" * 78)
    runs = []
    i = 0
    while i < nblk:
        if ok_block[i]:
            j = i
            while j + 1 < nblk and ok_block[j + 1]:
                j += 1
            if j - i + 1 >= 64:
                runs.append((i, j - i + 1))
            i = j + 1
        else:
            i += 1
    runs.sort(key=lambda r: -r[1])
    print(f"  找到 {len(runs)} 个 run")
    print(f"  {'起始':>14} {'块数':>7} {'字节':>9} {'原版此区非FF':>13}")
    for start_blk, cnt in runs[:20]:
        off = start_blk * 32
        seg_j = ja[off:off + cnt * 32]
        nz = sum(1 for b in seg_j if b != 0xFF)
        print(f"  0x{BASE+off:08X} {cnt:>7} {cnt*32:>9,} {nz:>13}")

    # ── ③ 对最大的 run，画字形 ─────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 画最大 run 的前 8 个 32B 块")
    print("=" * 78)
    if not runs:
        print("  无")
        return 0

    for start_blk, cnt in runs[:2]:
        off = start_blk * 32
        print(f"\n  ==== 0x{BASE+off:08X}（{cnt} 块）====")
        for k in range(8):
            blob = zh[off + k * 32: off + (k + 1) * 32]
            u = sorted(set(v for b in blob for v in (b & 0xF, b >> 4)))
            print(f"\n  块{k}  nibble={u}  {blob[:16].hex(' ')}")
            for y in range(8):
                row = blob[y * 4:(y + 1) * 4]
                line = ""
                for x in range(8):
                    b = row[x // 2]
                    v = (b & 0xF) if x % 2 == 0 else (b >> 4)
                    line += "." if v == 0 else str(v)
                print("    " + line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
