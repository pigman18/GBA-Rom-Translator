#!/usr/bin/env python3
"""调研(182) 排除「上半表 / 下半表分开存放」的可能，并做归一化格式穷举。

═══════════════════════════════════════════════════════════════════════════
【为什么要试这个】
═══════════════════════════════════════════════════════════════════════════
(181) 把「上半32B + 下半32B」当**连续 64B** 搜 ROM，32 种编码组合全 0 命中。

但 GBA 汉化常见一种布局：**上下半分别存在两张表里**
  · 表A：所有字的上半，stride = 32（或 8）
  · 表B：所有字的下半，同样 stride
两张表在 ROM 里相距很远，所以「连续 64B」永远搜不到。

【本脚本的三层排查】
 L1 **半部独立搜索**：对每种编码，单独搜上半 32B / 下半 32B（不拼接）
    若命中，检查这些偏移是否落在**等距序列**上（stride 8/16/32/64/128）
    → 等距 = 找到表了
 L2 **归一化格式**：VRAM 里是 10/11/12 三阶灰度，ROM 里可能存 0/1/2
    试 (bg,aa,core) → (0,1,2) 的 4bpp 与 2bpp 归一化
 L3 **半部偏移矩阵**：对每个字记录上半命中地址与下半命中地址，
    检查「下半 - 上半」是否为**常量**（=两表的固定间距）

【判定】
 真字库：某编码下命中数 ≥10，且偏移落在等距序列（stride 恒定）
 假阳性：命中数 ≤3，偏移随机散布

用法：python scripts/research/firered/182_half_tables.py
"""
from __future__ import annotations

import json
import struct
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
OUT = ROOT / "work" / "_probe" / "gsearch182"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"

SCREEN_BASE = 0xF000


def tile_nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0x0F) if x % 2 == 0 else (v >> 4)
    return m


def entry(vr: bytes, r: int, c: int) -> int:
    return struct.unpack_from("<H", vr, SCREEN_BASE + (r * 32 + c) * 2)[0]


def pack4(m: np.ndarray) -> bytes:
    b = bytearray(32)
    for y in range(8):
        for x in range(8):
            v = int(m[y, x]) & 0x0F
            if x % 2 == 0:
                b[y * 4 + x // 2] |= v
            else:
                b[y * 4 + x // 2] |= v << 4
    return bytes(b)


def pack2(m: np.ndarray) -> bytes:
    """8x8 2bpp → 16 字节。"""
    b = bytearray(16)
    for y in range(8):
        for x in range(8):
            v = int(m[y, x]) & 0x03
            b[y * 2 + x // 4] |= v << ((3 - (x % 4)) * 2)
    return bytes(b)


def pack1(m01: np.ndarray, msb: bool = True) -> bytes:
    out = bytearray()
    for y in range(8):
        v = 0
        for x in range(8):
            if m01[y, x]:
                v |= 1 << ((7 - x) if msb else x)
        out.append(v)
    return bytes(out)


def norm3(m: np.ndarray) -> np.ndarray:
    """10/11/12 → 0/1/2。"""
    o = np.zeros_like(m)
    o[m == 10] = 0
    o[m == 11] = 1
    o[m == 12] = 2
    return o


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    vr = (SNAP / "vram.bin").read_bytes()

    # ── 收集 8x16 字形 ────────────────────────────────────
    text_rows = [r for r in range(20)
                 if any(((entry(vr, r, c) >> 12) & 0xF) == 15 for c in range(30))]
    start = text_rows[0]
    gs = []
    for r in range(start, 19, 2):
        for c in range(30):
            et = entry(vr, r, c)
            if ((et >> 12) & 0xF) != 15:
                continue
            eb = entry(vr, r + 1, c)
            ot, ob = (et & 0x3FF) * 32, (eb & 0x3FF) * 32
            if ot + 32 > len(vr) or ob + 32 > len(vr):
                continue
            top = tile_nibs(vr[ot:ot + 32])
            bot = tile_nibs(vr[ob:ob + 32])
            ink = int((top == 12).sum() + (top == 11).sum()
                      + (bot == 12).sum() + (bot == 11).sum())
            if 4 <= ink <= 80:
                gs.append({"top": top, "bot": bot, "ink": ink,
                           "r": r, "c": c})
    print(f"真实字形 {len(gs)} 个")

    rom = ROM_ZH.read_bytes()
    rom_or = ROM_OR.read_bytes()

    # ── L1/L2/L3：半部独立搜索 ────────────────────────────
    encs: dict[str, callable] = {
        "4bpp-raw": pack4,
        "4bpp-norm012": lambda m: pack4(norm3(m)),
        "2bpp-norm012": lambda m: pack2(norm3(m)),
        "1bpp-core12": lambda m: pack1((m == 12).astype(np.uint8)),
        "1bpp-core12-L": lambda m: pack1((m == 12).astype(np.uint8), False),
        "1bpp-1112": lambda m: pack1(((m == 11) | (m == 12)).astype(np.uint8)),
        "1bpp-1112-L": lambda m: pack1(((m == 11) | (m == 12)).astype(np.uint8), False),
        "1bpp-any": lambda m: pack1(((m == 11) | (m == 12)).astype(np.uint8)),
    }

    print("\n" + "=" * 78)
    print("L1 半部独立搜索（不拼接上下半）")
    print("=" * 78)

    report: dict[str, dict] = {}
    for ename, fn in encs.items():
        row = {"top_hits": 0, "bot_hits": 0, "top_offs": [], "bot_offs": []}
        for i, g in enumerate(gs):
            pt = fn(g["top"])
            pb = fn(g["bot"])
            it = rom.find(pt)
            ib = rom.find(pb)
            if it >= 0:
                row["top_hits"] += 1
                row["top_offs"].append(it)
            if ib >= 0:
                row["bot_hits"] += 1
                row["bot_offs"].append(ib)
        report[ename] = row
        print(f"  {ename:<14} 上半 {row['top_hits']:>3}/{len(gs)}  "
              f"下半 {row['bot_hits']:>3}/{len(gs)}")

    # ── 等距判定 ─────────────────────────────────────────
    print("\n" + "=" * 78)
    print("L2 命中偏移是否等距（真字库的特征）")
    print("=" * 78)
    found = False
    for ename, row in report.items():
        for half in ("top", "bot"):
            offs = sorted(set(row[f"{half}_offs"]))
            if len(offs) < 5:
                continue
            gaps = [b - a for a, b in zip(offs, offs[1:])]
            gc = Counter(gaps)
            g, n = gc.most_common(1)[0]
            print(f"  {ename:<14} {half:<4} 命中 {len(offs):>3}  "
                  f"最多间隔 {g:>4}B x{n}")
            if n >= 4 and g <= 512:
                found = True
                print(f"    ★★★ 等距表候选！间隔 {g}B "
                      f"地址 {[hex(x) for x in offs[:10]]}")

    # ── L3 上下半间距是否常量 ────────────────────────────
    print("\n" + "=" * 78)
    print("L3 「下半地址 - 上半地址」是否为常量（两表固定间距）")
    print("=" * 78)
    for ename, row in report.items():
        if len(row["top_offs"]) < 5 or len(row["bot_offs"]) < 5:
            continue
        tos = sorted(set(row["top_offs"]))
        bos = sorted(set(row["bot_offs"]))
        diffs = Counter()
        for t in tos:
            for b in bos:
                diffs[b - t] += 1
        d, n = diffs.most_common(1)[0]
        print(f"  {ename:<14} 常见间距 {d:>8} x{n} "
              f"（上 {len(tos)} / 下 {len(bos)}）")

    if not found:
        print("\n  ✘ 没有任何编码在半部独立搜索下呈现等距表结构")
        print("     ⇒ 字形不是「两张半表」布局")

    # ── 附加：汉化 vs 原版，命中位置是否只在新增区 ────────
    print("\n" + "=" * 78)
    print("附加：4bpp-raw 命中的 8 个位置，在原版里是什么")
    print("=" * 78)
    row = report["4bpp-raw"]
    for o in sorted(set(row["top_offs"]))[:10]:
        same = rom_or[o:o + 32] == rom[o:o + 32]
        nz_or = sum(1 for b in rom_or[o:o + 32] if b)
        print(f"  0x{o:08X}  原版逐字节相同={same}  原版非零={nz_or}/32")

    (OUT / "report.json").write_text(
        json.dumps({k: {kk: (vv if not isinstance(vv, list) else vv[:32])
                        for kk, vv in v.items()} for k, v in report.items()},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {OUT / 'report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
