#!/usr/bin/env python3
"""调研㊱ 决定性验证 Q5：原版物种名表有没有被汉化改动。

═══════════════════════════════════════════════════════════════════════════
【为什么这是关键】
═══════════════════════════════════════════════════════════════════════════
用户的原话：
  「一些旧日版汉化版，和常规日版串档时，会出现宝可梦名乱码问题，
    因为它们是**宝可梦那块写入了汉化内容**，导致存档也乱了」

⇒ 要答 Q5，只需回答一件事：
   **火红有没有在原版物种名表的位置写中文？**

  · 若没写（原表原样保留）→ 存档拿到的是原版编码 → 串档不乱 ✓
  · 若写了 → 就一定乱，与用户描述冲突，说明有别的机制

═══════════════════════════════════════════════════════════════════════════
【方法：先找到原版物种名表，再逐字节比对】
═══════════════════════════════════════════════════════════════════════════
Gen3 物种名表铁特征（与语言无关）：
  · 每项定长 11 字节（POKEMON_NAME_LENGTH 10 + 终止符）
  · 不足 10 字符的项用 0xFF 填充到第 10 字节，第 11 字节也是 0xFF
    ⇒ **每项最后两个字节都是 FF**（这是很强的判据）
  · 连续 300+ 项
  · 内容非空项占比高（火红 386 可用 + 空槽）

本脚本用「末两字节均 FF + 连续 ≥300 项 + 内容项占比 ≥80%」搜，
然后对比原版与汉化。

用法：python scripts/research/firered/36_species_name_check.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
SPECIES, REC = 412, 11


def find_tables(rom: bytes, name: str) -> list[tuple[int, int, float]]:
    a = np.frombuffer(rom, dtype=np.uint8)
    n = len(a)
    # 每项最后两字节都是 0xFF
    ff = (a == 0xFF)
    end_ok = np.zeros(n, dtype=bool)
    m = n - REC
    end_ok[:m] = ff[REC - 2:m + REC - 2] & ff[REC - 1:m + REC - 1]
    # 起点必须不是 FF（内容非空）
    start_ok = np.zeros(n, dtype=bool)
    start_ok[:m] = ~ff[:m]

    cand = np.flatnonzero(end_ok[:m] & start_ok[:m])
    out = []
    for o in cand.tolist():
        good = 0
        nonempty = 0
        for k in range(SPECIES):
            b0 = o + k * REC
            if b0 + REC > n:
                break
            if not end_ok[b0]:
                break
            good += 1
            if not ff[b0]:
                nonempty += 1
        if good >= 300 and nonempty / max(1, good) >= 0.80:
            out.append((o, good, nonempty / good))
    # 去掉重叠（相邻起点会连续命中）
    out.sort()
    dedup = []
    for o, g, r in out:
        if dedup and o - dedup[-1][0] < REC:
            continue
        dedup.append((o, g, r))
    print(f"  {name}: 命中 {len(dedup)} 处")
    return dedup


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))

    print("=" * 78)
    print("找原版物种名表（末两字节 FF + ≥300 项 + 非空占比 ≥80%）")
    print("=" * 78)
    tj = find_tables(ja, "原版 BPRJ")
    for o, g, r in tj[:10]:
        print(f"    0x{BASE+o:08X}  {g} 项  非空占比 {r:.1%}")

    if not tj:
        print("\n  没找到。改用放宽判据：只要求末字节 FF + ≥300 项 + 非空 ≥80%")
        a = np.frombuffer(ja, dtype=np.uint8)
        ff = (a == 0xFF)
        m = len(a) - REC
        end_ok = np.zeros(len(a), dtype=bool)
        end_ok[:m] = ff[REC - 1:m + REC - 1]
        start_ok = np.zeros(len(a), dtype=bool)
        start_ok[:m] = ~ff[:m]
        cand = np.flatnonzero(end_ok[:m] & start_ok[:m])
        out = []
        for o in cand.tolist():
            good = 0
            nonempty = 0
            for k in range(SPECIES):
                b0 = o + k * REC
                if b0 + REC > len(a) or not end_ok[b0]:
                    break
                good += 1
                if not ff[b0]:
                    nonempty += 1
            if good >= 300 and nonempty / max(1, good) >= 0.80:
                out.append((o, good, nonempty / good))
        out.sort()
        dedup = []
        for o, g, r in out:
            if dedup and o - dedup[-1][0] < REC:
                continue
            dedup.append((o, g, r))
        tj = dedup
        print(f"    放宽后命中 {len(tj)} 处")
        for o, g, r in tj[:10]:
            print(f"      0x{BASE+o:08X}  {g} 项  非空 {r:.1%}")

    if not tj:
        print("\n  仍找不到 ⇒ 火红物种名不是 412×11 连续表，布局不同")
        return 0

    # ── 逐字节比对 ─────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("逐字节比对：原版物种名表 vs 汉化")
    print("=" * 78)
    for o, g, r in tj[:6]:
        size = g * REC
        a = ja[o:o + size]
        b = zh[o:o + size]
        diff = sum(1 for x, y in zip(a, b) if x != y)
        nf7 = b.count(0xF7)
        print(f"\n  表 @0x{BASE+o:08X}（{g} 项，{size:,} 字节）")
        print(f"    与原版不同：{diff:,} 字节（{diff/len(a)*100:.2f}%）")
        print(f"    汉化侧 F7 数：{nf7}")
        if diff == 0:
            print(f"    ⇒ **完全未改** ⇒ 存档里拿到的是原版编码 ⇒ 串档不乱 ✓")
        else:
            print(f"    ⇒ 有改动，前 6 项：")
            for k in range(6):
                ra = a[k*REC:(k+1)*REC]
                rb = b[k*REC:(k+1)*REC]
                print(f"      [{k}] {'同' if ra==rb else '★异'} "
                      f"原 {ra.hex(' ')}  汉 {rb.hex(' ')}")

    # ── 附：汉化的中文名表在哪 ─────────────────────────────────────
    print("\n" + "=" * 78)
    print("汉化新增的中文名表（0x0871F446）与原版表的关系")
    print("=" * 78)
    o = tj[0][0]
    print(f"  原版表位置：0x{BASE+o:08X}")
    print(f"  中文名表位置：0x0871F446")
    print(f"  两者相同？{o == 0x71F446}")
    print(f"  原版 0x0871F446 区内容：全 FF = {set(ja[0x71F446:0x71F446+0x1000]) == {0xFF}}")
    print(f"\n  ⇒ 若原版表在 A 且未被改，中文名表在 B 且原版是空的，")
    print(f"     则汉化只**新增了一张显示表**，原表与存档结构不动 ⇒ 串档不乱")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
