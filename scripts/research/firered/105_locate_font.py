#!/usr/bin/env python3
"""调研(105) 定位字库：命中集中在 0x0843E9A4，间隔 0x20 —— 那就是字库。

═══════════════════════════════════════════════════════════════════════════
【(104) 的突破】
═══════════════════════════════════════════════════════════════════════════
4bpp 原样搜索 1197 个 VRAM 字形，命中 151 个，且集中在：
     0x0843E9A4, 0x0843E9C4, 0x0843E9E4, 0x0843EA04, 0x0843EA44 ...
     **间隔 0x20 = 32 字节 = 一个 4bpp 8×8 tile！**

⇒ **ROM 0x0843Exxx 起就是字库**，格式与 VRAM 完全一致（4bpp 32B/tile）。

这也解释了为什么之前搜不全：(96) 只试了 6 个 tile，
而那 6 个恰好不在这个区（它们在 VRAM 里是被 palette 重绘过的）。

【本脚本】
 ① 精确找出字库的起止地址
 ② 按 32 字节/tile 切，画出前若干个，确认是汉字
 ③ 数出字库有多少个字形
 ④ 导出成完整字库大图

用法：python scripts/research/firered/105_locate_font.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
LOAD = ROOT / "work" / "_probe" / "glyphload"
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            b = blob[y * 4 + x // 2]
            m[y, x] = (b & 0x0F) if x % 2 == 0 else (b >> 4)
    return m


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()

    # 收集 VRAM 字形
    glyphs = set()
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
                glyphs.add(blob)

    print("=" * 78)
    print("① 收集所有命中位置")
    print("=" * 78)
    hits = []
    for g in glyphs:
        i = zh.find(g)
        while i >= 0:
            hits.append(i)
            i = zh.find(g, i + 1)
    hits.sort()
    print(f"  总命中 {len(hits)} 处")

    # 按 0x10000 分桶
    from collections import Counter
    c = Counter(h // 0x10000 for h in hits)
    print(f"  按 64KB 分布：")
    for k, v in c.most_common(12):
        print(f"    0x{BASE+k*0x10000:08X}: {v} 处")

    # ── ② 找最密集的区域边界 ────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 找字库区边界")
    print("=" * 78)
    if not c:
        print("  无命中")
        return 0
    top = c.most_common(1)[0][0]
    lo = top * 0x10000
    seg_hits = [h for h in hits if lo <= h < lo + 0x10000]
    print(f"  最密集 64KB：0x{BASE+lo:08X}，命中 {len(seg_hits)}")
    if seg_hits:
        print(f"  命中范围：0x{BASE+min(seg_hits):08X} .. "
              f"0x{BASE+max(seg_hits):08X}")

    # 按 0x1000 细分
    c2 = Counter(h // 0x1000 for h in seg_hits)
    print(f"  按 4KB 细分：")
    for k, v in sorted(c2.items(), key=lambda x: -x[1])[:10]:
        print(f"    0x{BASE+k*0x1000:08X}: {v} 处")

    # ── ③ 从最密集的 4KB 块开始，向前后扩展，找出连续区 ─────────
    print("\n" + "=" * 78)
    print("③ 确定字库起止（找「每 0x20 一个有效 tile」的连续区）")
    print("=" * 78)

    def is_glyph_tile(off: int) -> bool:
        if off + 32 > len(zh):
            return False
        blob = zh[off:off + 32]
        nib = set(nibs(blob).flatten().tolist())
        return bool(nib & {11, 12})

    # 从最密集的命中点向前后扫
    if not seg_hits:
        return 0
    center = sorted(seg_hits)[len(seg_hits) // 2]
    # 对齐到 32
    center = center - (center % 32)
    start = center
    while start - 32 >= 0 and is_glyph_tile(start - 32):
        start -= 32
    end = center
    while end + 32 <= len(zh) and is_glyph_tile(end):
        end += 32
    print(f"  从 0x{BASE+center:08X} 扩展：")
    print(f"    起 0x{BASE+start:08X}   止 0x{BASE+end:08X}")
    print(f"    共 {(end-start)//32} 个 32B tile")

    # ── ④ 画前 12 个 tile ──────────────────────────────────────
    print("\n" + "=" * 78)
    print("④ 画字库前 12 个 tile")
    print("=" * 78)
    for k in range(min(12, (end - start) // 32)):
        blob = zh[start + k * 32: start + (k + 1) * 32]
        m = nibs(blob)
        u = sorted(set(m.flatten().tolist()))
        print(f"\n  tile {k} @0x{BASE+start+k*32:08X}  nibble={u}")
        for y in range(8):
            print("    " + "".join(
                "#" if m[y, x] >= 12 else ("+" if m[y, x] == 11 else ".")
                for x in range(8)))

    # ── ⑤ 对照原版 ──────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("⑤ 原版同区域")
    print("=" * 78)
    seg_j = ja[start:min(end, start + 0x800)]
    print(f"  原版 0x{BASE+start:08X} 起 0x800 字节，非 FF："
          f"{sum(1 for b in seg_j if b != 0xFF)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
