#!/usr/bin/env python3
"""调研(128) 定案：0x0871Axxx 是字库，0x0871BFB0 是它的索引表。

═══════════════════════════════════════════════════════════════════════════
【(127) 的决定性发现】
═══════════════════════════════════════════════════════════════════════════
0x0871BFB0（汉化新增 6,177 字节）的内容：
    b8 3c 20 08 | 2c a4 71 08 | 3c a4 71 08 | 48 a4 71 08 | 54 a4 71 08 ...
    = 0x08203CB8, 0x0871A42C, 0x0871A43C, 0x0871A448, 0x0871A454 ...

⇒ 这是一张**指针表**，目标全部落在 **0x0871A42C 起**且地址递增！
   递增步长 0x10/0xC/0xC/0xC… 不等 ⇒ 变长项（正是字形！）

而 0x0871Axxx 之前被我当成「中文名表」（(33) 发现 0x0871F446 是名表）。
**0x0871A42C 与 0x0871F446 只差 0x5000** —— 同一大区的不同部分。

【本脚本】
 ① 读这张指针表的完整内容（项数、目标范围）
 ② 看目标处的数据（是不是 4bpp 字形）
 ③ 画出来

用法：python scripts/research/firered/128_font_index_found.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
TBL = 0x71BFB0


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))

    print("=" * 78)
    print("① 指针表 0x0871BFB0 的完整内容")
    print("=" * 78)
    ptrs = []
    off = TBL
    while off + 4 <= n:
        v = struct.unpack_from("<I", zh, off)[0]
        if not (BASE <= v < BASE + n):
            break
        ptrs.append(v)
        off += 4
    print(f"  有效指针：{len(ptrs)} 个")
    if ptrs:
        print(f"  首个 0x{ptrs[0]:08X}  末个 0x{ptrs[-1]:08X}")
        offs = [p - BASE for p in ptrs]
        print(f"  目标范围 0x{BASE+min(offs):08X} .. 0x{BASE+max(offs):08X}")
        gaps = np.diff(offs)
        from collections import Counter
        gc = Counter(gaps.tolist())
        print(f"  间隔分布 top8：{gc.most_common(8)}")
        print(f"\n  前 12 项：")
        for k in range(min(12, len(ptrs))):
            print(f"    [{k:>3}] 0x{ptrs[k]:08X}")

    # ── ② 看目标处的数据 ──────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 目标处的数据（前 6 项）")
    print("=" * 78)
    for k in range(min(6, len(ptrs))):
        o = ptrs[k] - BASE
        blob = zh[o:o + 64]
        nz = sum(1 for b in blob if b != 0xFF)
        print(f"\n  [{k}] 0x{ptrs[k]:08X}  非FF {nz}/64")
        print(f"      {blob.hex(' ')}")

    # ── ③ 这些目标在汉化 vs 原版 ──────────────────────────────
    print("\n" + "=" * 78)
    print("③ 目标区在汉化 vs 原版")
    print("=" * 78)
    if ptrs:
        s = min(offs)
        e = max(offs) + 64
        a = ja[s:e]
        b = zh[s:e]
        diff = sum(1 for x, y in zip(a, b) if x != y)
        print(f"  区间 0x{BASE+s:08X}..0x{BASE+e:08X}（{len(a):,} B）")
        print(f"  原版非FF：{sum(1 for x in a if x != 0xFF):,} / {len(a):,}")
        print(f"  汉化非FF：{sum(1 for x in b if x != 0xFF):,} / {len(b):,}")
        print(f"  差异：{diff:,} 字节")

    # ── ④ 画几个目标的数据 ────────────────────────────────────
    print("\n" + "=" * 78)
    print("④ 每项数据画出来（假设是 4bpp 字形）")
    print("=" * 78)
    for k in range(min(4, len(ptrs))):
        o = ptrs[k] - BASE
        nxt = ptrs[k + 1] - BASE if k + 1 < len(ptrs) else o + 128
        size = nxt - o
        blob = zh[o:o + min(size, 128)]
        print(f"\n  ==== [{k}] 0x{ptrs[k]:08X}  项长 {size} B ====")
        # 按 32B（8×8 tile）画
        for t in range(min(size // 32, 4)):
            tb = blob[t * 32:(t + 1) * 32]
            if len(tb) < 32:
                break
            print(f"    tile {t}:")
            for y in range(8):
                row = tb[y * 4:(y + 1) * 4]
                line = ""
                for x in range(8):
                    b = row[x // 2]
                    v = (b & 0xF) if x % 2 == 0 else (b >> 4)
                    line += "." if v == 0 else "#"
                print("      " + line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
