#!/usr/bin/env python3
"""调研(127) 把所有「新增区」按大小排序，逐个定性 —— 找出 281KB 的字库。

═══════════════════════════════════════════════════════════════════════════
【要解决的问题】
═══════════════════════════════════════════════════════════════════════════
汉化新增 648,523 字节。已确认：
  · F7 文本区约 344,064 字节
  · 剩余约 304,459 字节 ← 字库应该在这里

但按「nibble ≤3」扫只找到 844 个合格块（无连续 run）。

⇒ 说明我对「字形」的格式假设错了。可能是：
   a) 字形数据里 nibble 不只有 0/1/2（可能有 3 或更高）
   b) 字形前有个头/索引，混在一起
   c) 字库确实在这些区，但我的「块对齐」错了

【最稳的做法：不假设格式，把每个新增区**整块 dump 出来人眼看**】
 按大小排序，取最大的 10 个新增区，每个导出前 512 字节的 hex，
 以及「nibble 直方图」。人眼一看就知道是什么。

用法：python scripts/research/firered/127_dump_added_zones.py
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
    zh = np.frombuffer(FR_ZH.read_bytes(), dtype=np.uint8)
    ja = np.frombuffer(FR_JA.read_bytes(), dtype=np.uint8)
    n = min(len(zh), len(ja))

    added = (ja[:n] == 0xFF) & (zh[:n] != 0xFF)

    print("=" * 78)
    print("① 找连续的新增区（≥ 4KB）")
    print("=" * 78)
    runs = []
    i = 0
    while i < n:
        if added[i]:
            j = i
            while j + 1 < n and added[j + 1]:
                j += 1
            if j - i + 1 >= 4096:
                runs.append((i, j - i + 1))
            i = j + 1
        else:
            i += 1
    runs.sort(key=lambda r: -r[1])
    print(f"  找到 {len(runs)} 个（≥4KB）")
    print(f"  {'起始':>14} {'字节':>9} {'F7占比':>7} {'nibble直方图(0-15)'}")
    for off, ln in runs[:20]:
        seg = zh[off:off + ln]
        f7 = float((seg == 0xF7).mean())
        hi = seg >> 4
        lo = seg & 0x0F
        c = Counter(hi.tolist())
        c2 = Counter(lo.tolist())
        # 合并 nibble 直方图
        hist = [c.get(k, 0) + c2.get(k, 0) for k in range(16)]
        tot = sum(hist)
        compact = " ".join(f"{h*100//max(1,tot):>2}" for h in hist)
        print(f"  0x{BASE+off:08X} {ln:>9,} {f7:>6.1%}  {compact}")

    # ── ② 挑几个最大的，看前 512 字节 ──────────────────────────
    print("\n" + "=" * 78)
    print("② 最大的 5 个区，前 256 字节")
    print("=" * 78)
    for off, ln in runs[:5]:
        print(f"\n  ---- 0x{BASE+off:08X}（{ln:,} 字节）----")
        for k in range(0, 256, 32):
            blob = zh[off + k:off + k + 32]
            print(f"    +0x{k:03X}: {blob.tobytes().hex(' ')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
