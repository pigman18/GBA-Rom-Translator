#!/usr/bin/env python3
"""调研㊷ 补 U-1：定位原版物种名表（0x08204xxx 那片），确认汉化没改它。

═══════════════════════════════════════════════════════════════════════════
【㊶ 的线索】
═══════════════════════════════════════════════════════════════════════════
指针表 0x08419E38 起，原版值指向 **0x08204xxx** 一带，汉化改指 0x0871F5xx。
    [0] 原 0x08204B00 → 汉 0x0871FD84   内容 6c 77 a0 5c 85        (5 字节)
    [1] 原 0x082046D8 → 汉 0x0871F534   内容 02 01 02 38 28        (5 字节)
    [3] 原 0x08204890 → 汉 0x0871F8A4   内容 06 02 28 07           (4 字节)

这正是「名字指针表」：每项 u32 指向一条名字。
⇒ **原版物种名就在 0x08204xxx**，之前扫 412×11 连续数组当然找不到，
   因为它是指针表，不是压缩数组。

本脚本：
 ① 确认 0x08419E38 这张表的项数、步长、是否正好 412 项
 ② 统计「原版在 0x08204xxx 的名字」与「汉化在 0x0871F5xx 的名字」一一对应
 ③ **核心验证**：原版 0x08204xxx 那些名字字节，汉化有没有改
    —— 这是「串档不乱」的最后一块拼图

用法：python scripts/research/firered/42_species_table_u1.py
"""
from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
TBL = 0x419E38


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))
    m = n // 4 * 4
    pa = np.frombuffer(ja[:m], dtype=np.uint32).astype(np.uint64)
    pz = np.frombuffer(zh[:m], dtype=np.uint32).astype(np.uint64)

    print("=" * 78)
    print("① 表 0x08419E38 的真实结构")
    print("=" * 78)
    # 判断步长：相邻项是否 4 或 8 字节
    for stride in (4, 8, 12):
        vals_o = []
        vals_n = []
        for k in range(412):
            o = TBL + k * stride
            if o // 4 >= len(pa):
                break
            vals_o.append(int(pa[o // 4]))
            vals_n.append(int(pz[o // 4]))
        ok_o = sum(1 for v in vals_o if BASE <= v < BASE + n)
        ok_n = sum(1 for v in vals_n if BASE <= v < BASE + n)
        # 前 20 项的目标是否连续递增（名字通常连续存放）
        tg = [v - BASE for v in vals_o if BASE <= v < BASE + n][:20]
        inc = sum(1 for i in range(len(tg) - 1) if tg[i + 1] > tg[i])
        print(f"  步长 {stride}: 原版 {ok_o}/412 是ROM指针，汉化 {ok_n}/412；"
              f"前20项递增 {inc}/{max(1,len(tg)-1)}")

    # 用步长 4 详查
    print(f"\n  按步长 4 详解（前 20 项）：")
    print(f"  {'#':>4} {'原版指向':>12} {'汉化指向':>12} {'原版内容':>26} {'长度':>4}")
    for k in range(20):
        o = TBL + k * 4
        po = int(pa[o // 4]) - BASE
        pn = int(pz[o // 4]) - BASE
        if not (0 <= po < n):
            print(f"  {k:>4} 0x{po:08X} (非ROM)")
            continue
        e = ja.find(b"\xff", po, po + 60)
        content = ja[po:e] if e > 0 else ja[po:po + 12]
        print(f"  {k:>4} 0x{BASE+po:08X} 0x{BASE+pn:08X} "
              f"{content.hex(' '):>26} {len(content):>4}")

    # ── ② 覆盖面 ───────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 这张表覆盖多少条名字")
    print("=" * 78)
    tg = []
    for k in range(420):
        o = TBL + k * 4
        if o // 4 >= len(pa):
            break
        po = int(pa[o // 4]) - BASE
        if 0 <= po < n:
            tg.append(po)
    print(f"  有效项 {len(tg)}")
    if tg:
        print(f"  目标范围 0x{BASE+min(tg):08X}..0x{BASE+max(tg):08X}")
        c = Counter(x // 0x100 for x in tg)
        print(f"  按 256B 分桶 top8："
              + ", ".join(f"0x{BASE+k*0x100:08X}:{v}"
                          for k, v in c.most_common(8)))

    # ── ③ 核心：原版名字字节有没有被改 ────────────────────────────
    print("\n" + "=" * 78)
    print("③ 核心验证：原版 0x08204xxx 的名字，汉化有没有改")
    print("=" * 78)
    same = 0
    diff = 0
    only_ff = 0
    examples = []
    for po in tg:
        e = ja.find(b"\xff", po, po + 60)
        if e < 0:
            continue
        L = e - po + 1
        a = ja[po:po + L]
        b = zh[po:po + L]
        if a == b:
            same += 1
        elif set(zh[po:po + L]) == {0xFF}:
            only_ff += 1
            if len(examples) < 5:
                examples.append((po, L, a, b))
        else:
            diff += 1
            if len(examples) < 8:
                examples.append((po, L, a, b))

    tot = same + diff + only_ff
    print(f"  检查 {tot} 条名字：")
    print(f"    逐字节相同：  {same:>5}（{same/max(1,tot)*100:>5.1f}%）")
    print(f"    被清成 FF：   {only_ff:>5}（{only_ff/max(1,tot)*100:>5.1f}%）")
    print(f"    被改成中文：  {diff:>5}（{diff/max(1,tot)*100:>5.1f}%）")
    for po, L, a, b in examples:
        tag = "清FF" if set(b) == {0xFF} else "改动"
        print(f"\n    0x{BASE+po:08X} L={L} [{tag}]")
        print(f"      原: {a.hex(' ')}")
        print(f"      汉: {b.hex(' ')}")

    print("\n" + "=" * 78)
    if diff == 0 and only_ff == 0:
        print("⇒ 原版名字字节**一个都没改** ⇒ 存档里的是原版编码 ⇒ 串档不乱 ✓")
    elif same / max(1, tot) > 0.95:
        print(f"⇒ {same/max(1,tot)*100:.1f}% 未改，极少数被动过")
    else:
        print("⇒ 原版名字区被大量改动，需要重新解释「串档不乱」")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
