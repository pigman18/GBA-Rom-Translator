#!/usr/bin/env python3
"""调研(84) 定案：中文字形尺寸与拼装方式 —— 渲染已成功，直接量。

═══════════════════════════════════════════════════════════════════════════
【里程碑】
═══════════════════════════════════════════════════════════════════════════
用「tilemap 表项的 pal 字段」渲染后，**画面完全还原**：
    继续游戏 / 主角 RED / 时间 22:04 / 图鉴 62只 / 徽章 7枚 / 开始新游戏
  与截图逐字一致（compare.png 上下两半肉眼无差）。

此前所有失败的唯一原因：我一直用 palette 0，而文字用 **palette 15**。

【已量到】
  文字行 y=11..21 → **高 11 px**
  笔画段 (26,36) (39,49) (52,62) (65,75) → **宽 11**
  起点间隔 13 → **步进 13**

⇒ 汉字是 **11×11 字形、水平步进 13**（= 11 + 2 间距）。

这与「8+4 / 4+8 拼 tile」完全不同：**火红的汉字是单个 11×11 字形，
不是两块 tile 拼的**。这直接回答了「12px 怎么实现」的问题。

═══════════════════════════════════════════════════════════════════════════
【本脚本要坐实三件事】
═══════════════════════════════════════════════════════════════════════════
 ① 一个汉字占几个 8×8 tile（11×11 至少跨 2×2 = 4 个 tile）
 ② 同一行的 tilemap 里，一个汉字对应几个连续的 tile 索引
 ③ 字形数据在 VRAM 里的排布方式（是否每个汉字单独 4 tile）

用法：python scripts/research/firered/84_glyph_metrics.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "glyphs"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def main() -> int:
    vram = (OUT / "g1.vram.bin").read_bytes()
    pal = (OUT / "g1.pal.bin").read_bytes()
    sb = 0xF000

    print("=" * 78)
    print("① tilemap 每行引用的 tile 序列（看汉字占几个 tile）")
    print("=" * 78)
    for row in (1, 2, 3):
        ents = [rd16(vram, sb + (row * 32 + c) * 2) for c in range(14)]
        print(f"\n  行{row}:")
        for c, e in enumerate(ents):
            t = e & 0x3FF
            p = (e >> 12) & 0xF
            print(f"    列{c:>2}: tile={t:>4} pal={p:>2} "
                  f"hf={(e>>10)&1} vf={(e>>11)&1}", end="")
            if c % 2 == 1:
                print()
        print()

    # ── ② 一个汉字的 4 个 tile 长什么样 ─────────────────────────────
    print("=" * 78)
    print("② 取 tile 1,2 / 25,26（对应第一个汉字的上下两半）")
    print("=" * 78)
    for name, tiles in (("tile 1", [1]), ("tile 2", [2]),
                        ("tile 25", [25]), ("tile 26", [26])):
        for t in tiles:
            blob = vram[t * 32:(t + 1) * 32]
            print(f"\n  {name}（0x{t*32:04X}）: {blob[:16].hex(' ')}")
            for y in range(8):
                rb = blob[y * 4:(y + 1) * 4]
                line = ""
                for x in range(8):
                    b = rb[x // 2]
                    p = (b & 0x0F) if x % 2 == 0 else (b >> 4)
                    line += "." if p == 0 else "#"
                print(f"    {line}")

    # ── ③ 假设汉字 = 2×2 tile 拼，验证 ─────────────────────────────
    print("\n" + "=" * 78)
    print("③ 验证「汉字 = 2×2 tile」：把 tile(1,2 / 25,26) 拼成 16×16")
    print("=" * 78)

    def tile_art(t: int) -> list[str]:
        blob = vram[t * 32:(t + 1) * 32]
        out = []
        for y in range(8):
            rb = blob[y * 4:(y + 1) * 4]
            line = ""
            for x in range(8):
                b = rb[x // 2]
                p = (b & 0x0F) if x % 2 == 0 else (b >> 4)
                line += "." if p == 0 else "#"
            out.append(line)
        return out

    combos = [
        ("tile1+tile2 上", None),
        ("tile1/2 与 25/26 拼", (1, 2, 25, 26)),
    ]
    # 拼 16×16：左上=1 右上=2 左下=25 右下=26
    tl, tr, bl, br = 1, 2, 25, 26
    a_tl, a_tr = tile_art(tl), tile_art(tr)
    a_bl, a_br = tile_art(bl), tile_art(br)
    print(f"\n  (tile{tl}, tile{tr} / tile{bl}, tile{br}) 拼 16×16：")
    for y in range(8):
        print(f"    {a_tl[y]} {a_tr[y]}")
    for y in range(8):
        print(f"    {a_bl[y]} {a_br[y]}")

    # ── ④ 校验：字形 11×11 落在 16×16 里的位置 ─────────────────────
    print("\n" + "=" * 78)
    print("④ 分析：11×11 字形如何在 16×16 空间里排布")
    print("=" * 78)
    grid = np.zeros((16, 16), dtype=int)
    for ty, tw in ((0, tl), (2, bl)):
        for dy in range(8):
            rb = vram[tw * 32 + dy * 4: tw * 32 + dy * 4 + 4]
            for dx in range(8):
                b = rb[dx // 2]
                p = (b & 0x0F) if dx % 2 == 0 else (b >> 4)
                grid[ty + dy, dx] = p
    for ty, tw in ((0, tr), (2, br)):
        for dy in range(8):
            rb = vram[tw * 32 + dy * 4: tw * 32 + dy * 4 + 4]
            for dx in range(8):
                b = rb[dx // 2]
                p = (b & 0x0F) if dx % 2 == 0 else (b >> 4)
                grid[ty + dy, 8 + dx] = p
    print(f"  拼好的 16×16（# = 有墨）：")
    for y in range(16):
        line = "".join("#" if grid[y, x] else "." for x in range(16))
        print(f"    {line}")

    # 找实际有墨的范围
    ys, xs = np.nonzero(grid)
    if len(ys):
        print(f"\n  有墨范围：y={ys.min()}..{ys.max()} "
              f"(高 {ys.max()-ys.min()+1})  "
              f"x={xs.min()}..{xs.max()} (宽 {xs.max()-xs.min()+1})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
