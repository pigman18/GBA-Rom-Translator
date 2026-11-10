#!/usr/bin/env python3
"""调研(126) 用「空间核算」定位字库 —— 304KB 剩余 vs 281KB 需要。

═══════════════════════════════════════════════════════════════════════════
【关键推算（(125) 补算）】
═══════════════════════════════════════════════════════════════════════════
汉化新增总量                648,523 B
减去 F7 文本区             ~344,064 B
剩余                       ~304,459 B

若字库 = 2200 字 × 4 tile × 32 B = **281,600 B**
⇒ 剩余 304KB **正好装得下**，余量 22,859 B（可能是表/代码）

**⇒ 字库必然在 ROM 里，是 4bpp 32B/tile 的连续数组。**

【为什么之前搜不到】
 我一直用「VRAM 字形的字节」去搜，但 VRAM 里的 nibble 是 **10/11/12**
 （palette 映射后）。ROM 里可能是**原始值**（0/1/2 或 0/1/2/3）。
 (110) 在 0x08FE4560 看到的正是 `22 21 21 22 11 11...`（nibble 1/2）。

⇒ 判据应该是：**连续 8800 个 32B 块，每块 nibble 都主要落在 0/1/2（或 0/1/2/3）**

 之前 (115) 用「必须含 1 且含 2」太严 —— 有些字块可能只有 2 没有 1
 （无抗锯齿的纯笔画块）。

【本脚本：放宽判据，按「连续大数组」找】
 判据：
  · 每块 32B 的 nibble 最大值 ≤ 3（允许 0/1/2/3）
  · 至少 10% 的像素非零（不是全空）
  · 连续 ≥ 2000 块（500 字以上）

用法：python scripts/research/firered/126_by_space_budget.py
"""
from __future__ import annotations

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
    nblk = n // 32

    print("=" * 78)
    print("① 逐块判定（放宽：nibble ≤3，非全零）")
    print("=" * 78)
    arr = np.frombuffer(zh[:nblk * 32], dtype=np.uint8).reshape(nblk, 32)
    hi = arr >> 4
    lo = arr & 0x0F
    mx = np.maximum(hi, lo)
    # 每块最大 nibble
    blk_max = mx.max(axis=1)
    # 每块非零像素数
    nz = ((hi > 0) | (lo > 0)).sum(axis=1)

    ok = (blk_max <= 3) & (nz >= 6)
    print(f"  合格块：{int(ok.sum()):,} / {nblk:,}")

    # ── ② 找连续 run ────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 连续 run（≥2000 块 = 500 字）")
    print("=" * 78)
    runs = []
    i = 0
    while i < nblk:
        if ok[i]:
            j = i
            while j + 1 < nblk and ok[j + 1]:
                j += 1
            if j - i + 1 >= 2000:
                runs.append((i, j - i + 1))
            i = j + 1
        else:
            i += 1
    runs.sort(key=lambda r: -r[1])
    print(f"  找到 {len(runs)} 个")
    print(f"  {'起始':>14} {'块数':>7} {'字节':>10} {'可装字数':>8} "
          f"{'原版非FF':>9}")
    for sb, cnt in runs[:15]:
        off = sb * 32
        seg_j = ja[off:off + cnt * 32]
        nzj = int(np.sum(np.frombuffer(seg_j, dtype=np.uint8) != 0xFF))
        print(f"  0x{BASE+off:08X} {cnt:>7} {cnt*32:>10,} {cnt//4:>8} "
              f"{nzj:>9}")

    # ── ③ 对最大的画出来 ───────────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 画最大的 run")
    print("=" * 78)
    for sb, cnt in runs[:3]:
        off = sb * 32
        seg_j = ja[off:off + min(cnt, 64) * 32]
        nzj = int(np.sum(np.frombuffer(seg_j, dtype=np.uint8) != 0xFF))
        tag = "★汉化新增" if nzj == 0 else f"原版有{nzj}非FF"
        print(f"\n  ==== 0x{BASE+off:08X}（{cnt} 块，{tag}）====")
        for k in range(6):
            blob = zh[off + k * 32: off + (k + 1) * 32]
            u = sorted(set(v for b in blob for v in (b & 0xF, b >> 4)))
            print(f"\n    块{k}  nibble={u}")
            for y in range(8):
                row = blob[y * 4:(y + 1) * 4]
                line = ""
                for x in range(8):
                    b = row[x // 2]
                    v = (b & 0xF) if x % 2 == 0 else (b >> 4)
                    line += "." if v == 0 else str(v)
                print("      " + line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
