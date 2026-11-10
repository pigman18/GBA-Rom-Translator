#!/usr/bin/env python3
"""调研(121) 严查 151 个命中：它们是否真的聚集在某个连续区？

═══════════════════════════════════════════════════════════════════════════
【之前漏掉的一步】
═══════════════════════════════════════════════════════════════════════════
(104) 用 VRAM 的 1197 个字形搜 ROM，4bpp 原样命中 151 个。
我看了命中位置就下结论「分散在多处，是巧合」，**但没做统计检验**。

正确做法：
 · 若那 151 个命中**随机分布**在 16MB 里，期望每个 64KB 区约 0.6 个
 · 若它们**聚集**在某几个区（每区几十个），那就不是巧合

这能直接判定：是巧合，还是真字库（只是被别的数据隔开）。

【本脚本】
 ① 重现 151 个命中
 ② 做「随机分布假设」的统计检验
 ③ 若是聚集，把该区全部 32B 块画出来，人工找字形

用法：python scripts/research/firered/121_hits_clustering.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
LOAD = ROOT / "work" / "_probe" / "glyphload"
ACC = ROOT / "work" / "_probe" / "accum"
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
BASE = 0x08000000


def main() -> int:
    zh = FR_ZH.read_bytes()
    n = len(zh)

    # 收集字形（全部快照）
    glyphs = set()
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
                    glyphs.add(blob)

    print("=" * 78)
    print(f"① 用 {len(glyphs)} 个字形搜 ROM")
    print("=" * 78)
    hits = []
    for g in glyphs:
        i = zh.find(g)
        while i >= 0:
            hits.append(i)
            i = zh.find(g, i + 1)
    hits.sort()
    print(f"  命中 {len(hits)} 处")

    # ── ② 统计聚集度 ──────────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 聚集检验：按 64KB 分区")
    print("=" * 78)
    c = Counter(h // 0x10000 for h in hits)
    nzone = n // 0x10000
    exp = len(hits) / nzone
    print(f"  ROM 有 {nzone} 个 64KB 区，若随机分布每区期望 {exp:.2f} 个")
    print(f"\n  实际分区（只列 ≥3 的）：")
    total_in_top = 0
    for k, v in c.most_common(20):
        if v < 3:
            break
        print(f"    0x{BASE+k*0x10000:08X}: {v} 处  "
              f"（{v/exp:.1f}× 期望）")
        total_in_top += v
    print(f"\n  前几名合计 {total_in_top} / {len(hits)}"
          f"（{total_in_top/max(1,len(hits))*100:.0f}%）")

    # 卡方检验（粗略）
    obs = np.array([c.get(z, 0) for z in range(nzone)], dtype=float)
    chi = ((obs - exp) ** 2 / exp).sum()
    print(f"\n  卡方统计量 {chi:.1f}（自由度 {nzone-1}）")
    print(f"  若随机分布，卡方应≈{nzone-1}")
    print(f"  ⇒ {'**显著聚集**（不是巧合）' if chi > nzone * 2 else '接近随机'}")

    # ── ③ 最密集区里，逐个 32B 块检查 ────────────────────────
    print("\n" + "=" * 78)
    print("③ 最密集区：逐块扫描，找出连续的字形段")
    print("=" * 78)
    if not c:
        return 0
    top = c.most_common(1)[0][0]
    lo, hi = top * 0x10000, (top + 1) * 0x10000
    print(f"  区 0x{BASE+lo:08X}..0x{BASE+hi:08X}")
    seg_hits = [h for h in hits if lo <= h < hi]
    print(f"  命中 {len(seg_hits)} 处，范围 "
          f"0x{BASE+min(seg_hits):08X}..0x{BASE+max(seg_hits):08X}")

    # 按 32B 对齐，看有多少个「已知字形」位置的 tile
    known = set()
    for h in seg_hits:
        known.add(h - (h % 32))
    print(f"  对齐到 32B 后：{len(known)} 个位置")

    # 画这些位置附近的块
    print(f"\n  打印前 8 个已知字形位置及其前后：")
    for k, off in enumerate(sorted(known)[:8]):
        print(f"\n    已知字形 @0x{BASE+off:08X}:")
        blob = zh[off:off + 32]
        for y in range(8):
            row = blob[y * 4:(y + 1) * 4]
            line = ""
            for x in range(8):
                b = row[x // 2]
                v = (b & 0xF) if x % 2 == 0 else (b >> 4)
                line += "." if v == 0 else ("#" if v >= 12 else "+")
            print("      " + line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
