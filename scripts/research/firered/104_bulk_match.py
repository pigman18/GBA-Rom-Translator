#!/usr/bin/env python3
"""调研(104) 用「1197 个已知字形」反查 ROM 字库。

═══════════════════════════════════════════════════════════════════════════
【现在手里有很强的锚点】
═══════════════════════════════════════════════════════════════════════════
(103) 从 5 个不同画面抓到 **1197 个不同的字形**（VRAM 快照）。
每个字形都有确定的 nibble 图（只有 10/11/12 三值）。

若 ROM 里存的是同格式（4bpp、nibble 10/11/12），那么在 ROM 里
**一定**能搜到这 1197 个 32 字节块中的一部分。

(96) 只试了 6 个块，全落空。但 6 个样本太少 —— 1197 个里只要有 1% 命中，
就说明格式对、只是位置不同。

【本脚本】
 ① 从 5 个 VRAM 快照里提取**全部** 1197 个字形（32 字节原始 bytes）
 ② 拿它们批量去 ROM 搜
 ③ 统计命中率；若有命中，定位字库区
 ④ 若全落空，试「去掉抗锯齿（把 11 当 10）」的版本、
    「把 12 当 1、其他当 0」的 1bpp 版本、以及各种重排

用法：python scripts/research/firered/104_bulk_match.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
LOAD = ROOT / "work" / "_probe" / "glyphload"
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
BASE = 0x08000000


def main() -> int:
    zh = FR_ZH.read_bytes()

    # ── ① 收集全部字形（32 字节）──────────────────────────────────
    print("=" * 78)
    print("① 从 5 个快照收集全部字形")
    print("=" * 78)
    glyphs = {}
    for tag in ("A_menu", "B_world", "C_start", "D_down", "E_back"):
        p = LOAD / f"{tag}.vram.bin"
        if not p.exists():
            continue
        v = p.read_bytes()
        for t in range(len(v) // 32):
            blob = v[t * 32:(t + 1) * 32]
            nib = set()
            for b in blob:
                nib.add(b & 0xF)
                nib.add(b >> 4)
            if nib & {11, 12}:
                glyphs[blob] = tag
    print(f"  唯字形（32B）：{len(glyphs)}")

    # ── ② 直接搜 ─────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 拿全部字形在 ROM 里搜（4bpp 原样）")
    print("=" * 78)
    hit_blocks = []
    for blob, tag in glyphs.items():
        i = zh.find(blob)
        if i >= 0:
            hit_blocks.append((i, blob, tag))
    print(f"  命中 {len(hit_blocks)} / {len(glyphs)}"
          f"（{len(hit_blocks)/max(1,len(glyphs))*100:.1f}%）")
    for off, blob, tag in hit_blocks[:10]:
        print(f"    0x{BASE+off:08X}  (来自 {tag})")

    # ── ③ 去掉抗锯齿（11→10）再搜 ────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 把抗锯齿 11 归一成 10 后再搜")
    print("=" * 78)

    def norm(blob: bytes) -> bytes:
        out = bytearray()
        for b in blob:
            lo = b & 0xF
            hi = b >> 4
            if lo == 11:
                lo = 10
            if hi == 11:
                hi = 10
            out.append((hi << 4) | lo)
        return bytes(out)

    hit2 = []
    for blob, tag in glyphs.items():
        nb = norm(blob)
        i = zh.find(nb)
        if i >= 0:
            hit2.append(i)
    print(f"  命中 {len(hit2)} / {len(glyphs)}")

    # ── ④ 转 1bpp（12→1, 其他→0）再搜 ───────────────────────────
    print("\n" + "=" * 78)
    print("④ 转 1bpp（深灰=1，其余=0，每行 1 字节）再搜")
    print("=" * 78)

    def to1bpp(blob: bytes) -> bytes:
        out = bytearray()
        for y in range(8):
            row = 0
            for x in range(8):
                b = blob[y * 4 + x // 2]
                v = (b & 0xF) if x % 2 == 0 else (b >> 4)
                row = (row << 1) | (1 if v == 12 else 0)
            out.append(row)
        return bytes(out)

    hit3 = []
    for blob, tag in glyphs.items():
        b1 = to1bpp(blob)
        if len(set(b1)) <= 1:
            continue          # 全空/全满，无意义
        i = zh.find(b1)
        if i >= 0:
            hit3.append(i)
    print(f"  命中 {len(hit3)} / {len(glyphs)}")

    # ── ⑤ 只看最独特的字形（墨量适中、不像字母）─────────────────
    print("\n" + "=" * 78)
    print("⑤ 只用「最独特」的字形搜（排除空白与纯色）")
    print("=" * 78)
    special = {}
    for blob, tag in glyphs.items():
        n12 = sum(1 for b in blob for nib in (b & 0xF, b >> 4) if nib == 12)
        n11 = sum(1 for b in blob for nib in (b & 0xF, b >> 4) if nib == 11)
        if 8 <= n12 <= 40 and n11 >= 2:
            special[blob] = tag
    print(f"  独特字形（深灰 8~40 且含抗锯齿）：{len(special)}")
    hit4 = 0
    ex = []
    for blob, tag in special.items():
        if zh.find(blob) >= 0:
            hit4 += 1
            if len(ex) < 5:
                ex.append((tag, blob.hex()))
    print(f"  命中 {hit4} / {len(special)}")
    for tag, h in ex:
        print(f"    {tag}: {h}")

    # ── ⑥ 结论 ──────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("⑥ 判读")
    print("=" * 78)
    if max(len(hit_blocks), len(hit2), len(hit3)) == 0:
        print("  **三种格式在 ROM 里都搜不到**")
        print("  ⇒ 字形不是从 ROM 静态位图加载的，是**运行时生成**的")
        print("     下一步应查：渲染代码如何从「原版日文字模」变形出汉字")
    else:
        print("  有命中 ⇒ 字库在 ROM，可继续定位完整表")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
