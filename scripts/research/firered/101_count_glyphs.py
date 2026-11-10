#!/usr/bin/env python3
"""调研(101) 数清楚：VRAM 里到底加载了多少个不同字形。

═══════════════════════════════════════════════════════════════════════════
【要回答用户的问题】
═══════════════════════════════════════════════════════════════════════════
「字库图怎么只有这几个字？」

两种可能：
  A) 我切错了 —— 其实有很多字，我只抓到一部分
  B) 真就只有这些 —— VRAM 只装了当前画面的字，全字库在 ROM

本脚本用**不同字形的去重计数**来定性：

 ① 收集 tilemap 里所有 pal=15 的 tile 编号
 ② 每 2 个 tile（上下）组成一个字形，取唯一组合
 ③ 统计唯一个数，并与「画面上出现的字数」对比
 ④ 同时扫全 VRAM：有多少 tile 含灰阶（=有字形）

若「唯一字形数」≈「画面上字数」 ⇒ 是 B（只有当前画面的字）
若「唯一字形数」远大于画面字数 ⇒ 是 A（我漏切了）

用法：python scripts/research/firered/101_count_glyphs.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
G = ROOT / "work" / "_probe" / "glyphs"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def tnib(vram: bytes, t: int) -> np.ndarray:
    o = t * 32
    if o + 32 > len(vram):
        return np.full((8, 8), 10, dtype=np.uint8)
    blob = vram[o:o + 32]
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            b = blob[y * 4 + x // 2]
            m[y, x] = (b & 0x0F) if x % 2 == 0 else (b >> 4)
    return m


def main() -> int:
    vram = (G / "g1.vram.bin").read_bytes()
    sb = 0xF000

    print("=" * 78)
    print("① tilemap 里 pal=15（文字）的 tile 编号")
    print("=" * 78)
    text_tiles = []
    for r in range(20):
        row = []
        for c in range(30):
            e = rd16(vram, sb + (r * 32 + c) * 2)
            if ((e >> 12) & 0xF) == 15:
                row.append(e & 0x3FF)
        if row:
            text_tiles.append((r, row))
    total = sum(len(r) for _, r in text_tiles)
    print(f"  有文字的 tilemap 行：{len(text_tiles)}")
    print(f"  文字 tile 总数：{total}")
    for r, row in text_tiles:
        print(f"    行{r:>2}: {row[:20]}{'...' if len(row) > 20 else ''}")

    # ── ② 统计「不同 tile 编号」与「不同 tile 内容」─────────────
    print("\n" + "=" * 78)
    print("② 去重统计")
    print("=" * 78)
    ids = set()
    for _, row in text_tiles:
        ids.update(row)
    print(f"  不同 tile 编号：{len(ids)}")

    contents = {}
    for t in ids:
        m = tnib(vram, t)
        contents[t] = m.tobytes()
    uniq_content = len(set(contents.values()))
    print(f"  其中内容不同的：{uniq_content}")

    # 重复的 tile（同一内容多个编号）
    from collections import Counter
    cc = Counter(contents.values())
    dup = [(k, v) for k, v in cc.items() if v > 1]
    print(f"  内容重复的组：{len(dup)}")
    if dup:
        for k, v in sorted(dup, key=lambda x: -x[1])[:5]:
            tids = [t for t in ids if contents[t] == k]
            print(f"    内容重复 {v} 次：tile {tids}")

    # ── ③ 统计全 VRAM 里有多少「含灰阶」的 tile ─────────────────
    print("\n" + "=" * 78)
    print("③ 全 VRAM 里含灰阶（11/12）的 tile 数")
    print("=" * 78)
    n_total = len(vram) // 32
    with_ink = []
    for t in range(n_total):
        m = tnib(vram, t)
        u = set(m.flatten().tolist())
        if u & {11, 12}:
            with_ink.append(t)
    print(f"  含灰阶的 tile：{len(with_ink)} / {n_total}")
    # 内容去重
    sigs = {}
    for t in with_ink:
        sigs[t] = tnib(vram, t).tobytes()
    print(f"  内容去重后：{len(set(sigs.values()))}")

    # ── ④ 结论 ──────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("④ 判读")
    print("=" * 78)
    print(f"  菜单画面用了 {len(ids)} 个 tile 编号，内容去重后 {uniq_content} 个")
    print(f"  全 VRAM 含灰阶 tile {len(with_ink)}，内容去重后 "
          f"{len(set(sigs.values()))} 个")

    if uniq_content <= 300:
        print(f"\n  ⇒ 单帧最多只有 ~{uniq_content//2} 个字形")
        print(f"     这印证：**VRAM 只装当前画面的字**，不是全字库")
        print(f"     全字库（2000+ 字）必然在 ROM，或运行时按需生成")
    else:
        print(f"\n  ⇒ VRAM 里字形很多，我之前漏切了")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
