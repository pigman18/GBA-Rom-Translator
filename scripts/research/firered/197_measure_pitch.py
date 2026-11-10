#!/usr/bin/env python3
"""调研(197) 精确测量字距与字宽 —— 验证「10 一套 / 12 一套」假设。

═══════════════════════════════════════════════════════════════════════════
【用户的关键假设】
═══════════════════════════════════════════════════════════════════════════
用户指出：应该有**两套像素**——10 宽一套、12 宽一套；2 宽的借用原版窄字。

这解释了此前所有搜索失败的根因：
  · (176)(180) 我一直按 **8px 宽（一个 tile）** 提取字形
  · 若真实字宽是 10 或 12，提取出来的就是**被裁掉的半边**
  · 拿残缺图案去 ROM 搜，必然 0 命中

【本脚本要测的三个量（纯测量，不预设结论）】
 M1 字距（pitch）：一行文字里，相邻字形的起始 x 间隔
 M2 字宽（ink width）：单个字形墨迹的实际水平跨度
 M3 字高（ink height）：墨迹纵向跨度

【方法：列投影 + 空隙分割】
 把一行文字拼成 240px 宽（30 tile x 8px）的画布，
 计算每列墨迹像素数 → 得到列投影。
 字形之间应有「零墨列」（空隙），据空隙切出每个字，
 量出每字的 (起点, 宽度)，再统计 pitch 分布。

【判定】
 pitch 恒为 8  → 字宽真是 8，此前结论成立，「两套」不成立
 pitch 恒为 10 → 10 宽一套；需再找 12 宽的一套
 pitch 混合    → 两套并存（用户假设成立）

 若 ink width 最大 > 8 → 字确实跨 tile，我此前的提取是残缺的

用法：python scripts/research/firered/197_measure_pitch.py
"""
from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
OUT = ROOT / "work" / "_probe" / "pitch197"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
SCREEN_BASE = 0xF000

INK = {11, 12}          # 墨迹（抗锯齿 + 笔画核心）


def tile_nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0x0F) if x % 2 == 0 else (v >> 4)
    return m


def entry(vr: bytes, r: int, c: int) -> int:
    return struct.unpack_from("<H", vr, SCREEN_BASE + (r * 32 + c) * 2)[0]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    vr = (SNAP / "vram.bin").read_bytes()

    text_rows = [r for r in range(20)
                 if any(((entry(vr, r, c) >> 12) & 0xF) == 15 for c in range(30))]
    start = text_rows[0]
    print(f"tilemap 文字行：{text_rows}   配对起点={start}")

    results = []
    for r in range(start, 19, 2):
        # 取该行 30 列（含非文字列，保留整幅宽度）
        tiles = []
        any_text = False
        for c in range(30):
            et = entry(vr, r, c)
            eb = entry(vr, r + 1, c)
            if ((et >> 12) & 0xF) == 15:
                any_text = True
                tiles.append((c, et & 0x3FF, eb & 0x3FF))
        if not any_text:
            continue

        # 拼 240px 宽 x 16px 高画布
        W = 30 * 8
        canvas = np.zeros((16, W), dtype=np.uint8)
        for c in range(30):
            et = entry(vr, r, c)
            eb = entry(vr, r + 1, c)
            for half, e in ((0, et), (1, eb)):
                t = e & 0x3FF
                o = t * 32
                if o + 32 > len(vr):
                    continue
                canvas[half * 8:(half + 1) * 8, c * 8:(c + 1) * 8] = \
                    tile_nibs(vr[o:o + 32])

        ink = np.isin(canvas, list(INK))
        col = ink.sum(axis=0)           # 列投影

        # 找连续零列 = 空隙
        nz = col > 0
        # 墨迹段
        segs = []
        i = 0
        while i < W:
            if not nz[i]:
                i += 1
                continue
            j = i
            while j < W and nz[j]:
                j += 1
            segs.append((i, j, j - i))
            i = j

        starts = [s[0] for s in segs]
        pitches = [b - a for a, b in zip(starts, starts[1:])]
        widths = [s[2] for s in segs]
        rows_ink = ink.any(axis=1)
        ys = np.flatnonzero(rows_ink)

        print(f"\n{'=' * 78}")
        print(f"行 r={r}  (tilemap 上排)")
        print(f"{'=' * 78}")
        print(f"  墨迹段数 = {len(segs)}")
        print(f"  起始 x  = {starts}")
        print(f"  pitch   = {pitches}")
        print(f"  段宽    = {widths}")
        print(f"  pitch 分布 = {dict(Counter(pitches))}")
        print(f"  段宽分布   = {dict(Counter(widths))}")
        if len(ys):
            print(f"  墨迹纵向 = y {ys[0]}..{ys[-1]}  (高 {ys[-1] - ys[0] + 1})")

        # 渲染该行（16 行）
        print(f"  画布（# = 笔画，+ = 抗锯齿）：")
        for y in range(16):
            line = ""
            for x in range(W):
                v = int(canvas[y, x])
                line += "#" if v == 12 else ("+" if v == 11 else " ")
            print("    " + line.rstrip())

        results.append({"row": r, "segs": len(segs), "starts": starts,
                        "pitches": pitches, "widths": widths})

    # ── 汇总 ────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("汇总判定")
    print("=" * 78)
    all_p = [p for r in results for p in r["pitches"]]
    all_w = [w for r in results for w in r["widths"]]
    print(f"  全部 pitch：{dict(Counter(all_p).most_common(10))}")
    print(f"  全部段宽  ：{dict(Counter(all_w).most_common(10))}")
    print(f"  最大段宽 = {max(all_w) if all_w else 0}")
    if all_p:
        mode_p = Counter(all_p).most_common(1)[0][0]
        print(f"  最常见 pitch = {mode_p}")
    (OUT / "pitch.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {OUT / 'pitch.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
