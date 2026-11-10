#!/usr/bin/env python3
"""调研㉝ 确认 0x0871F446 是宝可梦名表，并回答「串档不乱」机制。

═══════════════════════════════════════════════════════════════════════════
【㉜ 发现】
═══════════════════════════════════════════════════════════════════════════
0x0871F446 起是**等长定宽表**：每项若干 00 补齐 + 中文名。
    [3] L=12  00 00 00 | f7 03 85 f7 01 ad f7 02 d9       ← 3 补 + 3 字
    [9] L=9   00 00 00 00 00 00 | f7 02 34                  ← 6 补 + 1 字

「00 补齐」= 右对齐定宽字段。这正是**名字表**的典型形态
（Gen3 名字字段 10 字节，不足右对齐 / 左对齐补 00）。

═══════════════════════════════════════════════════════════════════════════
【本脚本要坐实三件事】
═══════════════════════════════════════════════════════════════════════════
 ① 该表每项的真实步长（找块内真正的项边界）
 ② 项数是否 ≈ 火红物种数（412 含空槽，实际可用 386）
 ③ 原版对应位置是什么（若原版也是定宽表、且汉化把每项内容换成 F7，
    则说明**名字表被就地汉化**，那存档里的名字字段也被改了？
    还是说这张表只用于显示、存档另存一份？）
 ④ 铁证：查找「存档里的名字字段宽度」是否仍为原版（用 ROM 里的
    静态结构/初始化模板判断）

用法：python scripts/research/firered/33_name_table_proof.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
TABLE = 0x71F446


def main() -> int:
    zh_b = FR_ZH.read_bytes()
    ja_b = FR_JA.read_bytes()

    print("=" * 78)
    print("① 0x0871F446 的项边界与步长")
    print("=" * 78)
    off = TABLE
    # 逐字节看：找到所有 f7 起点，记录「最后一个汉字三元组结束位置」
    seg = zh_b[off:off + 0x4000]
    # 项边界猜测：每项以 ff 结尾；先统计 ff 的间隔
    ffs = [i for i, b in enumerate(seg) if b == 0xFF]
    print(f"  0x4000 字节内 ff 数量：{len(ffs)}")
    if len(ffs) > 2:
        gaps = [ffs[i + 1] - ffs[i] for i in range(len(ffs) - 1)]
        gc = Counter(gaps)
        print(f"  ff 间隔分布 top10：")
        for g, c in gc.most_common(10):
            print(f"    间隔 {g:>3} × {c}")

    # 直接列出前 30 项的「原始 24 字节窗口」，看结构
    print(f"\n  前 30 项（按 ff 切，附项起始的绝对地址）：")
    pos = 0
    items = []
    while pos < len(seg) and len(items) < 30:
        e = seg.find(b"\xff", pos)
        if e < 0:
            break
        items.append((pos, e - pos, seg[pos:e]))
        pos = e + 1
    for k, (p, L, body) in enumerate(items):
        n_ch = body.count(0xF7)
        n_pad = L - n_ch * 3
        print(f"    [{k:>3}] +0x{p:04X} L={L:<3} 汉字{n_ch} 补位{n_pad:<2} "
              f"{body.hex(' ')}")

    # ── ② 项数与步长 ───────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 尝试用「固定步长」拟合这张表")
    print("=" * 78)
    # 项起点 = 每个 ff 之后
    starts = []
    pos = 0
    while pos < len(seg):
        e = seg.find(b"\xff", pos)
        if e < 0:
            break
        starts.append(e + 1)
        pos = e + 1
    starts = [s for s in starts if s < len(seg)]
    if len(starts) >= 10:
        ds = [starts[i + 1] - starts[i] for i in range(len(starts) - 1)]
        dc = Counter(ds)
        print(f"  相邻项起点差值分布 top8：")
        for d, c in dc.most_common(8):
            print(f"    步长 {d:>3} × {c}")
        print(f"  ⇒ 若某个步长占绝对多数，那就是定宽表的步长")

    # ── ③ 原版对应位置 ─────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 原版 0x0871F446 处是什么")
    print("=" * 78)
    a = ja_b[off:off + 0x400]
    b = zh_b[off:off + 0x400]
    print(f"  原版前 96 字节: {a[:96].hex(' ')}")
    print(f"  汉化前 96 字节: {b[:96].hex(' ')}")
    print(f"  原版该区是否全 FF：{set(a) == {0xFF}}")
    # 原版该区非 FF 的字节数
    nz = sum(1 for x in a if x != 0xFF)
    print(f"  原版该 0x400 字节里非 FF：{nz}")
    # 整块 0x4000
    a2 = ja_b[off:off + 0x4000]
    print(f"  原版该 0x4000 字节里非 FF："
          f"{sum(1 for x in a2 if x != 0xFF):,}")

    # ── ④ 找「名字字段 10 字节」的存档结构 ─────────────────────────
    print("\n" + "=" * 78)
    print("④ 存档里的名字字段宽度：在 ROM 里找 10 字节名字模板")
    print("=" * 78)
    # Gen3 宝可梦子结构 / 队伍结构中名字字段为 10 字节 + 1 终止。
    # 直接判据：找「汉化版里 0x0871F446 附近的中文名」是否也以
    # 「10 字节定宽」出现过一次（那可能是写入存档的模板）
    # 更直接：数一数全 ROM 有多少「连续 f7 三元组 + 定宽 00 补齐」的块
    print("  统计全 ROM「右对齐补 00 的中文定宽串」分布：")
    hits = Counter()
    i = 0
    n = len(zh_b)
    while i < n - 24:
        if zh_b[i] == 0x00 and zh_b[i + 1] == 0x00 and zh_b[i + 2] == 0x00:
            # 找 00...00 之后紧跟若干 f7 三元组，再跟 ff
            j = i
            while j < n and zh_b[j] == 0x00:
                j += 1
            if j > i:
                k = j
                cnt2 = 0
                while k + 2 < n and zh_b[k] == 0xF7:
                    k += 3
                    cnt2 += 1
                if cnt2 >= 1 and k < n and zh_b[k] == 0xFF:
                    hits[(i // 0x10000)] += 1
                    i = k + 1
                    continue
        i += 1
    print(f"    总命中 {sum(hits.values()):,} 处")
    for seg_, c in hits.most_common(12):
        print(f"      0x{BASE+seg_*0x10000:08X}  {c:>5} 处")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
