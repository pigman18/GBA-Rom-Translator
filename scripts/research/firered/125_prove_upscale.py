#!/usr/bin/env python3
"""调研(125) 定案：八字形是 8×8 放大而来 —— 找到源字模。

═══════════════════════════════════════════════════════════════════════════
【(124) 的决定性证据】
═══════════════════════════════════════════════════════════════════════════
VRAM 里 135 个字形，统计「水平相邻两像素都是墨」的占比：
    **均值 34.80%，中位 33.33%**

手工设计的 11×11 汉字，笔画应为 1px 宽（2px 宽占比 <20%）。
34.8% 强烈指向 **8×8 → 11×11 的 1.375 倍放大**：
  · 原 1px 笔画放大后约 1.375px，会出现大量 1-2px 混合
  · 原 2px 笔画放大会变成 2-3px

⇒ **字形 = 原版 8×8 日文字模放大 1.375 倍 + 抗锯齿**

这解释了一切：
  · ROM 里搜不到中文字库 → 因为没有中文字库
  · 只改了 F7 文本 → 因为只是把中文映射到原版字符
  · VRAM 字形 nibble 只有 10/11/12 → 放大+抗锯齿产生的三档灰度
  · 汉化新增代码区没有 VRAM 基址引用 → 因为渲染走原版代码

【本脚本：反向验证】
 ① 把 VRAM 里的 11×11 字形**缩小回 8×8**，看是否干净
 ② 若缩小后是干净的 8×8 位图 ⇒ 证实放大假设
 ③ 拿缩小后的 8×8 去 ROM 搜 ⇒ 应该能搜到！

用法：python scripts/research/firered/125_prove_upscale.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
LOAD = ROOT / "work" / "_probe" / "glyphload"
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()

    vram = (LOAD / "A_menu.vram.bin").read_bytes()

    # 说明：VRAM 里每 tile 8×8，汉字 11×11 跨 2×2 tile。
    # 先找到「文字 tile」（pal=15）的位置，再拼成 11×11。

    print("=" * 78)
    print("① 取几个字形，缩回 8×8 看是否干净")
    print("=" * 78)

    def downsample(g11: np.ndarray, out: int = 8) -> np.ndarray:
        """把 11×11（或 12×12）的布尔图缩到 8×8，用多数表决。"""
        h, w = g11.shape
        r = np.zeros((out, out), dtype=np.uint8)
        for y in range(out):
            for x in range(out):
                y0 = round(y * h / out)
                y1 = max(y0 + 1, round((y + 1) * h / out))
                x0 = round(x * w / out)
                x1 = max(x0 + 1, round((x + 1) * w / out))
                blk = g11[y0:y1, x0:x1]
                r[y, x] = 1 if blk.mean() >= 0.5 else 0
        return r

    # 用 glyphload 里已确认的 4 个字（继续游戏的 4 个字）
    # 从 harness 里已知：文字行 y=11..22，x=26,39,52,65
    # 但那是渲染后的坐标系；这里直接操作 VRAM tile。

    # 更简单：把 tilemap 里 pal=15 的每 2×2 tile 拼成 16×16，
    # 再裁 11×11，缩回 8×8
    import struct

    def rd16(b, o):
        return struct.unpack_from("<H", b, o)[0]

    def tile_nib(v, t):
        o = t * 32
        if o + 32 > len(v):
            return np.full((8, 8), 10, dtype=np.uint8)
        blob = v[o:o + 32]
        m = np.zeros((8, 8), dtype=np.uint8)
        for y in range(8):
            for x in range(8):
                b = blob[y * 4 + x // 2]
                m[y, x] = (b & 0xF) if x % 2 == 0 else (b >> 4)
        return m

    sb = 0xF000
    # 行 1 与 2 是第一条文字带（tile 1..24 与 25..48）
    results = []
    for col0 in range(2, 14, 1):
        e_up = rd16(vram, sb + (1 * 32 + col0) * 2)
        e_dn = rd16(vram, sb + (2 * 32 + col0) * 2)
        if ((e_up >> 12) & 0xF) != 15:
            continue
        up = tile_nib(vram, e_up & 0x3FF)
        dn = tile_nib(vram, e_dn & 0x3FF)
        cell = np.vstack([up, dn])          # 16×8
        # 判墨
        ink = (cell == 11) | (cell == 12)
        if ink.sum() < 4:
            continue
        g8 = downsample(ink, 8)
        results.append((col0, cell, ink, g8))

    print(f"  取到 {len(results)} 个")
    for i, (col0, cell, ink, g8) in enumerate(results[:4]):
        print(f"\n  === 第{i}个（col={col0}）===")
        print("  原始 16×8（# 笔画 / + 抗锯齿）：")
        for y in range(16):
            line = ""
            for x in range(8):
                v = cell[y, x]
                line += "." if v == 10 or v == 0 else ("#" if v == 12 else "+")
            print("    " + line)
        print("  缩回 8×8：")
        for y in range(8):
            print("    " + "".join("#" if g8[y, x] else "." for x in range(8)))

    # ── ② 拿缩回的 8×8 去 ROM 搜 ─────────────────────────────
    print("\n" + "=" * 78)
    print("② 把缩回的 8×8 转成 1bpp 8 字节，去 ROM 搜")
    print("=" * 78)
    hits = 0
    examples = []
    for col0, cell, ink, g8 in results:
        pat = bytearray()
        for y in range(8):
            row = 0
            for x in range(8):
                row = (row << 1) | int(g8[y, x])
            pat.append(row)
        pat = bytes(pat)
        if len(set(pat)) <= 1:
            continue
        i = zh.find(pat)
        if i >= 0:
            hits += 1
            if len(examples) < 5:
                examples.append((col0, i, pat.hex()))
    print(f"  命中 {hits} / {len(results)}")
    for col0, off, h in examples:
        print(f"    col={col0} → 0x{BASE+off:08X}  {h}")

    # ── ③ 结论 ───────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 判读")
    print("=" * 78)
    if hits > 0:
        print("  缩回 8×8 后能在 ROM 搜到")
        print("  ⇒ **证实：汉字 = 原版 8×8 字模放大**")
        print("  ⇒ 完整字库不存在，中文是用原版字库的字符组合出来的")
    else:
        print("  仍搜不到")
        print("  ⇒ 缩回后的 8×8 与原版字模格式不同（可能有位重排）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
