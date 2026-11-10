#!/usr/bin/env python3
"""调研(122) 提取 0x0836xxxx 的真实字库 —— 命中率 119 倍于随机。

═══════════════════════════════════════════════════════════════════════════
【决定性证据（(121)）】
═══════════════════════════════════════════════════════════════════════════
用 1489 个 VRAM 字形搜 ROM，命中 517 处，分布：
    0x08360000: 241 处  （**119.3 倍**于随机期望）
    0x08320000:  51 处  （25.3 倍）
    0x08430000:  46 处  （22.8 倍）
卡方 32280（自由度 255，随机应≈255）⇒ 极度聚集

主体在 0x0836B410..0x0836F744，222 个 32B 位置。

⚠ 但 (105) 我看这些块时觉得「像图标不像汉字」——
   那是因为我只看前几个块（0x0836D6E0 附近是别的数据）。

【本脚本：只提取「确认命中的」那些位置，拼成字库】
 ① 精确列出 0x0836xxxx 里哪些 32B 位置是已知字形
 ② 按位置排序，画出来
 ③ 若有 200+ 个，说明这是一个「按需加载页」而非全字库
 ④ 统计：这些字形覆盖多少个不同汉字

用法：python scripts/research/firered/122_extract_836.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
LOAD = ROOT / "work" / "_probe" / "glyphload"
ACC = ROOT / "work" / "_probe" / "accum"
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()

    # 收集字形
    glyphs = {}
    for d in (LOAD, ACC):
        if not d.exists():
            continue
        for f in d.glob("*.vram.bin"):
            v = f.read_bytes()
            for t in range(len(v) // 32):
                blob = v[t * 32:(t + 1) * 32]
                nib = set()
                for b in blob:
                    nib.add(b & 0xF)
                    nib.add(b >> 4)
                if nib & {11, 12}:
                    glyphs.setdefault(blob, f.stem)

    # 在 0x08360000 区搜
    print("=" * 78)
    print("① 0x08360000 区的命中位置")
    print("=" * 78)
    lo, hi = 0x360000, 0x370000
    found = {}
    for g, tag in glyphs.items():
        i = zh.find(g, lo, hi)
        while i >= 0:
            found[i] = g
            i = zh.find(g, i + 1)
    print(f"  命中 {len(found)} 处")
    offs = sorted(found)
    if offs:
        print(f"  范围 0x{BASE+offs[0]:08X} .. 0x{BASE+offs[-1]:08X}")
        # 对齐到 32
        aligned = sorted({o - (o % 32) for o in offs})
        print(f"  对齐后 {len(aligned)} 个位置")
        print(f"  前 30 个：{[f'0x{BASE+x:08X}' for x in aligned[:30]]}")

    # ── ② 检查这些位置是否等距 ────────────────────────────────
    print("\n" + "=" * 78)
    print("② 位置间距（等距 = 字库数组）")
    print("=" * 78)
    if len(aligned) > 2:
        gaps = np.diff(aligned)
        from collections import Counter
        gc = Counter(gaps.tolist())
        print(f"  间距分布 top10：{gc.most_common(10)}")

    # ── ③ 画这些位置 ──────────────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 打印前 12 个命中位置")
    print("=" * 78)
    for k in aligned[:12]:
        blob = zh[k:k + 32]
        n1 = sum(1 for b in blob for v in (b & 0xF, b >> 4) if 1 <= v <= 3)
        print(f"\n  0x{BASE+k:08X}  墨量(1-3)={n1}")
        for y in range(8):
            row = blob[y * 4:(y + 1) * 4]
            line = ""
            for x in range(8):
                b = row[x // 2]
                v = (b & 0xF) if x % 2 == 0 else (b >> 4)
                line += "." if v == 0 else ("#" if v >= 12 else
                                            ("+" if v == 11 else str(v)))
            print("    " + line)

    # ── ④ 这些位置在原版 vs 汉化的差异 ────────────────────────
    print("\n" + "=" * 78)
    print("④ 原版 vs 汉化")
    print("=" * 78)
    if aligned:
        s = aligned[0]
        e = aligned[-1] + 32
        a = ja[s:e]
        b = zh[s:e]
        diff = sum(1 for x, y in zip(a, b) if x != y)
        print(f"  区间 0x{BASE+s:08X}..0x{BASE+e:08X}")
        print(f"  改动 {diff:,} / {len(a):,} 字节（{diff/len(a)*100:.1f}%）")
        print(f"  ⇒ {'汉化改过这块' if diff > 0 else '**两版完全相同**'}")
        if diff == 0:
            print(f"     ⇒ 这是**原版就有的图形**，不是中文字库")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
