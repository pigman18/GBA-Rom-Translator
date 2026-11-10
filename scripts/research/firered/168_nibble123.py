#!/usr/bin/env python3
"""调研(168) 定案：字形用 nibble 1/2/3（不是 10/11/12），重新渲染。

═══════════════════════════════════════════════════════════════════════════
【(167) 的发现】
═══════════════════════════════════════════════════════════════════════════
按 tilemap 精确渲染后，字形里出现的是 **1 / 2 / 3**，不是 10/11/12。

回看 (164) 的 nibble 分布：
    VRAM  nibble 10 → 8%   12 → 1%   11 → 0%
   但这是**全 VRAM 的统计**，包含了大量非文字 tile。

真正的文字 tile（pal=15 的 288 个）里，字形是 **nibble 1/2/3**。

⇒ 这与我之前 (83) 用 palette15 映射成 10/11/12 的结果矛盾。
  原因：(83) 那次是**另一个画面**（也可能我把 palette 索引算重了）。

  正确理解应该是：
    · 字形存储用 nibble 1 / 2 / 3（1=浅灰, 2=深灰, 3=更浅?）
    · palette 15 把 1/2/3 映射成具体颜色

【本脚本】
 ① 用 nibble 1/2/3 直接渲染 pal=15 的 tile（不做任何映射）
 ② 拼出完整菜单文字，验证是否正确
 ③ 从 EWRAM 找 nibble 1/2/3 的块（不是 10/11/12）
 ④ 拿这些块去 ROM 搜

用法：python scripts/research/firered/168_nibble123.py
"""
from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            b = blob[y * 4 + x // 2]
            m[y, x] = (b & 0x0F) if x % 2 == 0 else (b >> 4)
    return m


def ch(v: int) -> str:
    if v == 0:
        return "."
    if v == 1:
        return "+"
    if v == 2:
        return "#"
    if v == 3:
        return "@"
    return str(v)


def main() -> int:
    vr = (SNAP / "vram.bin").read_bytes()
    ew = (SNAP / "ewram.bin").read_bytes()
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    SB = 0xF000

    # 收集 pal=15 的 tile
    tiles = {}
    for r in range(20):
        for c in range(30):
            e = rd16(vr, SB + (r * 32 + c) * 2)
            if ((e >> 12) & 0xF) == 15:
                tidx = e & 0x3FF
                off = tidx * 32
                if off + 32 <= len(vr):
                    tiles[tidx] = vr[off:off + 32]

    print("=" * 78)
    print(f"① pal=15 的 tile：{len(tiles)} 个")
    print("=" * 78)
    # 统计 nibble 分布
    c = Counter()
    for blob in tiles.values():
        for b in blob:
            c[b & 0xF] += 1
            c[b >> 4] += 1
    tot = sum(c.values())
    print(f"  nibble 分布：" +
          " ".join(f"{k}:{v*100//tot}%" for k, v in sorted(c.items())))

    # ── ② 渲染前 6 行 ─────────────────────────────────
    print("\n" + "=" * 78)
    print("② 渲染（nibble 3→@ 2→# 1→+ 0→. ）")
    print("=" * 78)
    for r in range(20):
        ents = [rd16(vr, SB + (r * 32 + c2) * 2) for c2 in range(30)]
        if not any(((e >> 12) & 0xF) == 15 for e in ents):
            continue
        canvas = np.zeros((8, 30 * 8), dtype=np.uint8)
        for c2 in range(30):
            e = ents[c2]
            if ((e >> 12) & 0xF) != 15:
                continue
            tidx = e & 0x3FF
            off = tidx * 32
            if off + 32 > len(vr):
                continue
            canvas[:, c2 * 8:(c2 + 1) * 8] = nibs(vr[off:off + 32])
        print(f"\n  行 {r}:")
        for y in range(8):
            print("    " + "".join(ch(canvas[y, x]) for x in range(30 * 8)))

    # ── ③ EWRAM 里找 nibble 1/2/3 的块 ────────────────
    print("\n" + "=" * 78)
    print("③ EWRAM 里找 nibble ⊆ {0,1,2,3} 且有墨的 32B 块")
    print("=" * 78)
    cand = []
    for off in range(0, len(ew) - 32, 32):
        blob = ew[off:off + 32]
        u = set(v for b in blob for v in (b & 0xF, b >> 4))
        if u <= {0, 1, 2, 3}:
            ink = sum(1 for b in blob for v in (b & 0xF, b >> 4) if v)
            if ink >= 8:
                cand.append((off, blob))
    print(f"  候选 {len(cand)} 块")

    # ── ④ 去 ROM 搜 ─────────────────────────────────
    print("\n" + "=" * 78)
    print("④ 拿去 ROM 搜")
    print("=" * 78)
    hits = []
    for off, blob in cand:
        i = zh.find(blob)
        if i >= 0:
            hits.append((off, i, blob))
    print(f"  命中 {len(hits)} / {len(cand)}")
    for eoff, roff, blob in hits[:12]:
        same = ja[roff:roff + 32] == blob
        print(f"    EWRAM 0x{0x02000000+eoff:08X} → ROM 0x{BASE+roff:08X}  "
              f"{'原版相同' if same else '★汉化新增'}")
    if hits:
        z = Counter(h[1] // 0x10000 for h in hits)
        print(f"\n  按 64KB：")
        for k, v in z.most_common(8):
            print(f"    0x{BASE+k*0x10000:08X}: {v}")

    # ── ⑤ 也拿 VRAM 里的文字 tile 去 ROM 搜 ──────────
    print("\n" + "=" * 78)
    print("⑤ VRAM 的文字 tile 去 ROM 搜")
    print("=" * 78)
    hits2 = []
    for tidx, blob in tiles.items():
        i = zh.find(blob)
        if i >= 0:
            hits2.append((tidx, i))
    print(f"  命中 {len(hits2)} / {len(tiles)}")
    if hits2:
        z2 = Counter(h[1] // 0x10000 for h in hits2)
        print(f"  按 64KB：")
        for k, v in z2.most_common(8):
            print(f"    0x{BASE+k*0x10000:08X}: {v}")
        for tidx, roff in hits2[:10]:
            print(f"    tile {tidx} → ROM 0x{BASE+roff:08X}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
