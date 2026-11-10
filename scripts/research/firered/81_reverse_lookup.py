#!/usr/bin/env python3
"""调研(81) 反查：哪个 tilemap 引用了「几乎满」的 tile（文字候选）。

═══════════════════════════════════════════════════════════════════════════
【突破口】
═══════════════════════════════════════════════════════════════════════════
(80) 把 VRAM 的 3072 个 4bpp tile 分类：
    全00     2711
    几乎满    289   ← 之前一直忽略！
    中等墨量   72   ← 全是菜单边框

「几乎满」的 289 个 tile，其 nibble 值是 10,10（即 0xAA），
在 4bpp 里 10 = 调色板第 10 号色。**如果调色板第 10 号色是深灰，
那这些 tile 在屏幕上就是深色块 —— 但文字笔画恰恰需要深色。**

⚠ 但 0xAA 是「未初始化 VRAM 填充」的典型标记，未必是字。
  必须**反查 tilemap**：只有被 tilemap 引用的 tile 才会显示。

【做法】
 对每个可能的 screenBase（0..0x1F × 0x800，共 32 个）：
   统计它的 tilemap 里引用了多少「几乎满」tile、多少「中等墨量」tile
 引用率最高的那个就是真实 BG tilemap。
 然后把它的前几行渲染出来看。

用法：python scripts/research/firered/81_reverse_lookup.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "glyphs"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def classify(vram: bytes) -> dict[int, str]:
    """给每个 4bpp tile 分类。"""
    kinds = {}
    for k in range(len(vram) // 32):
        blob = vram[k * 32:(k + 1) * 32]
        s = set(blob)
        if s <= {0x00}:
            kinds[k] = "全00"
            continue
        if s <= {0xAA}:
            kinds[k] = "全AA"
            continue
        ink = sum(1 for b in blob for nib in (b & 0xF, b >> 4) if nib)
        if ink >= 57:
            kinds[k] = "几乎满"
        elif ink < 6:
            kinds[k] = "几乎空"
        else:
            kinds[k] = "中等"
    return kinds


def main() -> int:
    vram = (OUT / "g1.vram.bin").read_bytes()
    pal = (OUT / "g1.pal.bin").read_bytes()
    kinds = classify(vram)

    from collections import Counter
    print("=" * 78)
    print("① tile 分类结果")
    print("=" * 78)
    c = Counter(kinds.values())
    for k, n in c.most_common():
        print(f"  {k:<8} {n:>5}")

    full = [k for k, v in kinds.items() if v == "几乎满"]
    mid = [k for k, v in kinds.items() if v == "中等"]
    print(f"\n  几乎满：{len(full)} 个，前 30 = {full[:30]}")
    print(f"  中等：  {len(mid)} 个，前 30 = {mid[:30]}")

    # ── ② 反查 tilemap ────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 反查：哪个 screenBase 的 tilemap 引用了这些 tile")
    print("=" * 78)
    full_set = set(full)
    mid_set = set(mid)
    best = []
    for sb in range(0, 0x8000, 0x800):
        if sb + 0x800 > len(vram):
            break
        n_full = n_mid = n_used = 0
        for i in range(0x400):      # 32×32 表项
            ent = rd16(vram, sb + i * 2)
            tidx = ent & 0x3FF
            if tidx == 0:
                continue
            n_used += 1
            if tidx in full_set:
                n_full += 1
            elif tidx in mid_set:
                n_mid += 1
        if n_used:
            best.append((n_full, n_mid, n_used, sb))
    best.sort(reverse=True)
    print(f"  {'screenBase':>12} {'引用tile':>8} {'几乎满':>7} {'中等':>6}")
    for nf, nm, nu, sb in best[:10]:
        print(f"  0x{sb:04X}        {nu:>8} {nf:>7} {nm:>6}")

    if not best:
        print("  没有找到有效 tilemap")
        return 0

    # ── ③ 渲染引用最多的那个 ─────────────────────────────────────
    nf, nm, nu, sb = best[0]
    print("\n" + "=" * 78)
    print(f"③ 渲染 screenBase=0x{sb:04X} 的 tilemap（charBase=0x0000, 4bpp）")
    print("=" * 78)
    for row in range(4):
        print(f"\n  行 {row}（y={row*8}..{row*8+7}）:")
        ents = [rd16(vram, sb + (row * 32 + c) * 2) for c in range(30)]
        print(f"    tile: {[e & 0x3FF for e in ents[:16]]}")
        for ly in range(8):
            line = ""
            for cc in range(30):
                ent = ents[cc]
                tidx = ent & 0x3FF
                hf = (ent >> 10) & 1
                lx0 = 7 - ly if (ent >> 11) & 1 else ly
                to = tidx * 32
                if to + 32 > len(vram):
                    line += "?"
                    continue
                blob = vram[to:to + 32]
                rowb = blob[lx0 * 4:(lx0 + 1) * 4]
                x = 3 if hf else 4
                b = rowb[x // 2]
                px = (b & 0x0F) if x % 2 == 0 else (b >> 4)
                line += "." if px == 0 else "#"
            print(f"      |{line}|")

    # ── ④ 调色板第 10 号色是什么 ──────────────────────────────────
    print("\n" + "=" * 78)
    print("④ 调色板各号色（4bpp 的 16 色）")
    print("=" * 78)
    for i in range(16):
        v = rd16(pal, i * 2)
        r = (v & 0x1F) * 255 // 31
        g = ((v >> 5) & 0x1F) * 255 // 31
        b = ((v >> 10) & 0x1F) * 255 // 31
        print(f"  [{i:>2}] RGB({r:>3},{g:>3},{b:>3})   0x{v:04X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
