#!/usr/bin/env python3
"""调研(116) 找「谁往 0x08FE4560 暂存区写字」—— 那是字形的源头。

═══════════════════════════════════════════════════════════════════════════
【思路】
═══════════════════════════════════════════════════════════════════════════
 0x08FE4560 是 ROM 里的静态数据（原版 FF，汉化填了 636 字节）。
 ROM 是只读的，所以**这个暂存区不会被写**，它本身**就是字形数据**。

 只是它太小（~700 字节 = 约 5 个 4-tile 字形）。

 ⇒ 说明：**每次显示文字时，代码从这里取那几个字形，重复使用**。
    即：这几个字形是「模板」，或者是特定界面（继续游戏菜单）专用的。

【关键洞察】
 继续游戏菜单的字（继续游戏/主角/时间/图鉴/徽章/开始新游戏）共 17 个不同汉字。
 而 0x08FE4560 只有约 700 字节 ≈ 5 个 4-tile 字形。
 ⇒ 不匹配。

 除非：字形不是存在 0x08FE4560，而是**其中一部分**。
 或者 0x08FE4560 只是「第一次搬运」的临时数据。

【本脚本：查「汉化新增的全部字形数据」在哪】
 判据：原版 FF + 汉化有内容 + nibble 只含 0/1/2 的**字节序列**（不要求 32 对齐）
 这会找到所有含字形的区，再按大小排序。

用法：python scripts/research/firered/116_all_glyph_bytes.py
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

    print("=" * 78)
    print("① 扫「字节值 ⊆ {0x00,0x11,0x12,0x21,0x22,0x01,0x02,0x10,0x20}」的连续区")
    print("=" * 78)
    # 这些是 nibble 只含 0/1/2 的所有字节组合
    OK = {0x00, 0x01, 0x02, 0x10, 0x11, 0x12, 0x20, 0x21, 0x22}
    runs = []
    i = 0
    while i < n:
        if zh[i] in OK and ja[i] == 0xFF:      # 汉化有内容且原版空白
            j = i
            while j < n and zh[j] in OK and ja[j] == 0xFF:
                j += 1
            if j - i >= 64:                     # 至少 64 字节
                runs.append((i, j - i))
            i = j
        else:
            i += 1
    runs.sort(key=lambda r: -r[1])
    print(f"  找到 {len(runs)} 个区（≥64 字节）")
    print(f"  {'起始':>14} {'字节数':>8}")
    for off, ln in runs[:25]:
        print(f"  0x{BASE+off:08X} {ln:>8,}")
    print(f"\n  总计：{sum(ln for _, ln in runs):,} 字节")

    # ── ② 画最大的几个 ─────────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 画最大的 3 个区")
    print("=" * 78)
    for off, ln in runs[:3]:
        print(f"\n  ==== 0x{BASE+off:08X}（{ln} 字节）====")
        cnt = min(ln // 32, 6)
        for k in range(cnt):
            blob = zh[off + k * 32: off + (k + 1) * 32]
            n1 = sum(1 for b in blob for v in (b & 0xF, b >> 4) if v == 1)
            n2 = sum(1 for b in blob for v in (b & 0xF, b >> 4) if v == 2)
            print(f"\n    块{k} n1={n1} n2={n2}")
            for y in range(8):
                row = blob[y * 4:(y + 1) * 4]
                line = ""
                for x in range(8):
                    b = row[x // 2]
                    v = (b & 0xF) if x % 2 == 0 else (b >> 4)
                    line += "." if v == 0 else ("+" if v == 1 else "#")
                print("      " + line)

    # ── ③ 统计这些区的总字节，够放多少字 ───────────────────────
    print("\n" + "=" * 78)
    print("③ 总量评估")
    print("=" * 78)
    total = sum(ln for _, ln in runs)
    print(f"  字形类数据总计 {total:,} 字节")
    print(f"    若每字 4 tile（128 B）→ {total//128} 个字形")
    print(f"    若每字 2 tile（ 64 B）→ {total//64} 个字形")
    print(f"    若每字 1 tile（ 32 B）→ {total//32} 个字形")
    print(f"\n  火红中文约需 2000~2300 个字")
    for per in (128, 64, 32):
        need = 2200 * per
        print(f"    按每字 {per} B 算需 {need:,} B，"
              f"{'够' if total >= need else '**不够**'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
