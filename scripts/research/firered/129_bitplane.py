#!/usr/bin/env python3
"""调研(129) 位平面分离 —— 最后一个没试的可能。

═══════════════════════════════════════════════════════════════════════════
【为什么这个假设值得试】
═══════════════════════════════════════════════════════════════════════════
VRAM 里字形是 4bpp（每像素 4 bit，两个像素挤一字节）。
但如果 ROM 里按 **bitplane** 存：
    bit0 平面 8 字节 + bit1 平面 8 字节 + bit2 平面 8 字节 + bit3 平面 8 字节
    = 32 字节/tile，**同样大小，但字节排列完全不同**

⇒ 直接搜「VRAM 的 32 字节」必然搜不到！

这能完美解释我的困境：
  · 空间核算吻合（281KB = 2200 字 × 128B）
  · 但任何「按 4bpp 搜」都失败

【本脚本】
 ① 从 VRAM 取已知字形（nibble 10/11/12）
 ② 转换成 bitplane 格式
 ③ 在 ROM 里搜
 ④ 若命中，验证该区能否画出全部字形

用法：python scripts/research/firered/129_bitplane.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
LOAD = ROOT / "work" / "_probe" / "glyphload"
ACC = ROOT / "work" / "_probe" / "accum"
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
FR_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000


def to_bitplanes(blob: bytes) -> bytes:
    """4bpp 交错格式 → 4 个 bitplane（每平面 8 字节）。"""
    # 先取 8×8 nibble
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            b = blob[y * 4 + x // 2]
            m[y, x] = (b & 0x0F) if x % 2 == 0 else (b >> 4)
    out = bytearray()
    for bit in range(4):
        for y in range(8):
            row = 0
            for x in range(8):
                row = (row << 1) | ((m[y, x] >> bit) & 1)
            out.append(row)
    return bytes(out)


def main() -> int:
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()
    n = min(len(zh), len(ja))

    # 收集字形
    glyphs = set()
    for d in (LOAD, ACC):
        if not d.exists():
            continue
        for f in d.glob("*.vram.bin"):
            v = f.read_bytes()
            for t in range(len(v) // 32):
                blob = v[t * 32:(t + 1) * 32]
                nib = set()
                for b in blob:
                    nib.add(b & 0xF)
                    nib.add(b >> 4)
                if nib & {11, 12}:
                    glyphs.add(blob)
    print(f"① 收集 {len(glyphs)} 个字形")

    # ── ② 转 bitplane 搜 ──────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 转 bitplane 格式后搜 ROM")
    print("=" * 78)
    hits = []
    for g in glyphs:
        bp = to_bitplanes(g)
        i = zh.find(bp)
        while i >= 0:
            hits.append(i)
            i = zh.find(bp, i + 1)
    print(f"  命中 {len(hits)} 处")

    if hits:
        from collections import Counter
        c = Counter(h // 0x10000 for h in hits)
        print(f"  按 64KB 分布：")
        for k, v in c.most_common(10):
            print(f"    0x{BASE+k*0x10000:08X}: {v} 处")

    # ── ③ 也试「nibble 交换」「反色」等变体 ────────────────────
    print("\n" + "=" * 78)
    print("③ 其它可能的变换")
    print("=" * 78)

    def variants(blob: bytes):
        bp = to_bitplanes(blob)
        yield "bitplane", bp
        # nibble 交换
        sw = bytes(((b & 0xF) << 4) | (b >> 4) for b in blob)
        yield "nibble-swap", sw
        # 反色
        inv = bytes(b ^ 0xFF for b in blob)
        yield "invert", inv
        # 4bpp 但把 10/11/12 映射成 0/1/2
        mp = {}
        for v in range(16):
            mp[v] = {10: 0, 11: 1, 12: 2}.get(v, 0)
        norm = bytes((mp[b >> 4] << 4) | mp[b & 0xF] for b in blob)
        yield "norm-012", norm

    for name in ("bitplane", "nibble-swap", "invert", "norm-012"):
        cnt = 0
        ex = []
        for g in glyphs:
            for vn, pat in variants(g):
                if vn != name:
                    continue
                if len(set(pat)) <= 1:
                    continue
                i = zh.find(pat)
                if i >= 0:
                    cnt += 1
                    if len(ex) < 3:
                        ex.append(i)
        print(f"  {name:<12} 命中 {cnt:>4} / {len(glyphs)}  "
              f"{[f'0x{BASE+x:08X}' for x in ex]}")

    # ── ④ 若 bitplane 有命中，验证该区 ────────────────────────
    if hits:
        print("\n" + "=" * 78)
        print("④ 验证 bitplane 命中区")
        print("=" * 78)
        lo = min(hits) - (min(hits) % 32)
        print(f"  首个命中附近 0x{BASE+lo:08X}")
        blob = zh[lo:lo + 64]
        print(f"  {blob.hex(' ')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
