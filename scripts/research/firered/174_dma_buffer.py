#!/usr/bin/env python3
"""调研(174) 查 DMA 源缓冲区：EWRAM 0x020047F0 / 0x020053B0 里到底是什么。

═══════════════════════════════════════════════════════════════════════════
【为什么查这两个地址】
═══════════════════════════════════════════════════════════════════════════
(152) watchpoint 在中文菜单下稳定抓到 20 次，全部一致：
     PC = 0x08000DF4   （DMA3 启动点）
     R3 = 0x020047F0 或 0x020053B0   ← **DMA 源地址**
     R2 = 0x06000000 / 0x06004000    ← VRAM 目标

⇒ 送进 VRAM（变成我们看到的字形）的数据，**在这两个 EWRAM 缓冲里**。

而 (172) 我拿的是**按 13px 重切后的渲染结果**去 ROM 搜，那是错的
（13px 与 8px tile 不对齐，切出来的字节不是原始数据）。

【本脚本（纯离线，用 163 的快照）】
 ① 读 EWRAM 0x020047F0 / 0x020053B0 各 256 字节
 ② 按 4bpp 8×8 画出来，看是不是字形
 ③ 原样去 ROM 搜（汉化版 + 原版）
 ④ 也试多种归一化与位宽

用法：python scripts/research/firered/174_dma_buffer.py
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
ADDRS = [0x020047F0, 0x020053B0, 0x02002C40, 0x02002F40]


def nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            b = blob[y * 4 + x // 2]
            m[y, x] = (b & 0x0F) if x % 2 == 0 else (b >> 4)
    return m


def ch(v: int) -> str:
    return {0: ".", 10: " ", 11: "+", 12: "#"}.get(v, str(v))


def main() -> int:
    ew = (SNAP / "ewram.bin").read_bytes()
    vr = (SNAP / "vram.bin").read_bytes()
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()

    def at(addr: int, n: int) -> bytes:
        off = addr - 0x02000000
        return ew[off:off + n]

    print("=" * 78)
    print("① DMA 源缓冲内容")
    print("=" * 78)
    for addr in ADDRS:
        blob = at(addr, 128)
        nz = sum(1 for b in blob if b)
        u = sorted(set(v for b in blob for v in (b & 0xF, b >> 4)))
        print(f"\n  0x{addr:08X}  非零 {nz}/128  nibble={u[:10]}")
        print(f"    {blob[:64].hex(' ')}")

    # ── ② 按 4bpp 画前 4 个 tile ──────────────────────
    print("\n" + "=" * 78)
    print("② 画前 4 个 8×8 tile")
    print("=" * 78)
    for addr in ADDRS[:2]:
        print(f"\n  ==== 0x{addr:08X} ====")
        for t in range(4):
            blob = at(addr + t * 32, 32)
            if len(blob) < 32:
                break
            m = nibs(blob)
            print(f"\n    tile {t}:")
            for y in range(8):
                print("      " + "".join(ch(m[y, x]) for x in range(8)))

    # ── ③ 拿这些字节去两个 ROM 搜 ────────────────────
    print("\n" + "=" * 78)
    print("③ 去 ROM 搜（多种形式 × 多种长度）")
    print("=" * 78)

    def variants(blob: bytes):
        yield "raw", blob
        # 10/11/12 → 0/1/2
        yield "012", bytes(
            (({10: 0, 11: 1, 12: 2}.get(b >> 4, 0) << 4) |
             {10: 0, 11: 1, 12: 2}.get(b & 0xF, 0)) for b in blob)
        # 10/11/12 → 0/1/2 但 10 当 3
        yield "3/1/2", bytes(
            (({10: 3, 11: 1, 12: 2}.get(b >> 4, 0) << 4) |
             {10: 3, 11: 1, 12: 2}.get(b & 0xF, 0)) for b in blob)
        # 12 → 1，其余 0（1bpp，每行 1 字节）
        b1 = bytearray()
        for y in range(8):
            v = 0
            for x in range(8):
                b = blob[y * 4 + x // 2] if y * 4 + x // 2 < len(blob) else 0
                p = (b & 0xF) if x % 2 == 0 else (b >> 4)
                v = (v << 1) | (1 if p == 12 else 0)
            b1.append(v)
        yield "1bpp", bytes(b1)
        # 11 也算笔画
        b2 = bytearray()
        for y in range(8):
            v = 0
            for x in range(8):
                b = blob[y * 4 + x // 2] if y * 4 + x // 2 < len(blob) else 0
                p = (b & 0xF) if x % 2 == 0 else (b >> 4)
                v = (v << 1) | (1 if p in (11, 12) else 0)
            b1.append(v)
        yield "1bpp(含11)", bytes(b1)

    found_any = False
    for addr in ADDRS:
        for t in (0, 1, 2, 3):
            blob = at(addr + t * 32, 32)
            if len(blob) < 32 or len(set(blob)) <= 1:
                continue
            for vname, pat in variants(blob):
                if len(set(pat)) <= 1:
                    continue
                for rname, rom in (("汉化", zh), ("原版", ja)):
                    hits = []
                    i = rom.find(pat)
                    while i >= 0 and len(hits) < 10:
                        hits.append(i)
                        i = rom.find(pat, i + 1)
                    if hits:
                        found_any = True
                        print(f"  0x{addr:08X}+{t*32} [{vname}] 在{rname} "
                              f"命中 {len(hits)}: "
                              f"{[f'0x{BASE+h:08X}' for h in hits[:4]]}")

    if not found_any:
        print("  **全部 0 命中**")

    # ── ④ 反向查：VRAM 里的文字 tile 在 EWRAM 里有没有副本 ─
    print("\n" + "=" * 78)
    print("④ VRAM 文字 tile 在 EWRAM 里的副本")
    print("=" * 78)
    # 收集 VRAM 里 nibble 含 11/12 的 tile
    vtiles = {}
    for i in range(len(vr) // 32):
        b = vr[i * 32:(i + 1) * 32]
        u = set(v for x in b for v in (x & 0xF, x >> 4))
        if u & {11, 12}:
            vtiles[i] = b
    print(f"  VRAM 含笔画的 tile：{len(vtiles)}")
    hit = 0
    for i, b in list(vtiles.items())[:40]:
        j = ew.find(b)
        if j >= 0:
            hit += 1
            if hit <= 8:
                print(f"    VRAM tile {i} = EWRAM 0x{0x02000000+j:08X}")
    print(f"  在 EWRAM 找到副本：{hit}/40")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
