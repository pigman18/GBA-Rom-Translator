#!/usr/bin/env python3
"""调研(183) 在 RAM（EWRAM/IWRAM/VRAM）里搜 8x16 字形位图 —— 字库应在此。

═══════════════════════════════════════════════════════════════════════════
【(180)(181)(182) 推进出的关键认知】
═══════════════════════════════════════════════════════════════════════════
F1 汉字 = 8 宽 x 16 高（(180) 看图确证）
F2 charBase(0x06000000) 的布局是 **24 列 x 12 行 = 288 个 tile 的文字缓冲**：
   第 k 条文字行的上半 = charBase 第 2k 行，下半 = 第 2k+1 行
   （即 tile 序号 = 文本行*48 + 半*24 + 列）
F3 288 个 tile 里**只有 103 个有墨迹** ⇒ charBase 是「已渲染的文字层」，
   不是字库本身。
F4 32 种「上半32B+下半32B」连续 64B 格式 → **ROM 里 0 命中**（(181)）
F5 上下两半分表存放 → **也排出**（(182)）

⇒ 结论方向：字形是**运行时由 RAM 里的字库渲染进来的**。
   字库应在 EWRAM（262KB，非零 37,843B）或 IWRAM 里。

【本脚本】
 在 snap3 的 ewram.bin / iwram.bin / ewram_at_prove.bin 里，
 用多种 8x16 编码格式搜索「已知字形」，并检查命中是否等距成表。

 编码矩阵（8 宽 x 16 高，值取 {0,1,2} ← 由 nibble 10/11/12 归一）：
   F-2bpp-M  2bpp 行主序 16 字节  (每行 8px*2bit=16bit=2B)
   F-2bpp-L  同上，位序反转
   F-1bpp-M  1bpp 行主序 16 字节，core(12)→1
   F-1bpp-A  1bpp 行主序 16 字节，(11|12)→1
   F-1bpp-AL 同上位序反转
   F-4bpp-64 4bpp 行主序 64 字节（每行 8px*4bit=4B）
   F-planar  平面分离：16B plane0 + 16B plane1
   F-2bpp-T  转置（16 宽 x 8 高）再 2bpp

 另外：**不要求整字匹配**，也统计「单行 16 位 == 某行的 2bpp 编码」
 的命中密度，用来定位表的起始——因为表可能有 2 字节对齐/头部偏移。

【判定】
 命中数 ≥10 且地址等距 → 找到字库表，给出起始地址与 stride

用法：python scripts/research/firered/183_search_ram_font.py
"""
from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "work" / "_probe" / "snap3"
OUT = ROOT / "work" / "_probe" / "ramfont183"
SCREEN_BASE = 0xF000

RAM = {
    "ewram": (0x02000000, SNAP / "ewram.bin"),
    "ewram_prove": (0x02000000, SNAP / "ewram_at_prove.bin"),
    "iwram": (0x03000000, SNAP / "iwram.bin"),
    "vram": (0x06000000, SNAP / "vram.bin"),
}


def tile_nibs(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0x0F) if x % 2 == 0 else (v >> 4)
    return m


def entry(vr: bytes, r: int, c: int) -> int:
    return struct.unpack_from("<H", vr, SCREEN_BASE + (r * 32 + c) * 2)[0]


# ── 编码器（输入 16x8 的 0/1/2 矩阵）──────────────────────────
def enc_2bpp(m: np.ndarray, msb: bool = True) -> bytes:
    out = bytearray()
    for y in range(16):
        v = 0
        for x in range(8):
            val = int(m[y, x]) & 3
            if msb:
                v |= val << (14 - x * 2)
            else:
                v |= val << (x * 2)
        out += v.to_bytes(2, "big" if msb else "little")
    return bytes(out)


def enc_1bpp(m01: np.ndarray, msb: bool = True) -> bytes:
    out = bytearray()
    for y in range(16):
        v = 0
        for x in range(8):
            if m01[y, x]:
                v |= 1 << ((7 - x) if msb else x)
        out.append(v)
    return bytes(out)


def enc_4bpp(m: np.ndarray) -> bytes:
    out = bytearray()
    for y in range(16):
        for xb in range(4):
            b = 0
            for k in range(2):
                x = xb * 2 + k
                val = int(m[y, x]) & 0x0F
                b |= val if k == 0 else val << 4
            out.append(b)
    return bytes(out)


def enc_planar(m01: np.ndarray) -> bytes:
    p0 = bytearray()
    p1 = bytearray()
    for y in range(16):
        v0 = v1 = 0
        for x in range(8):
            v = int(m01[y, x]) & 3
            bit = 7 - x
            v0 |= ((v >> 0) & 1) << bit
            v1 |= ((v >> 1) & 1) << bit
        p0.append(v0)
        p1.append(v1)
    return bytes(p0) + bytes(p1)


def find_all(hay: bytes, needle: bytes, limit: int = 4000) -> list[int]:
    out = []
    i = hay.find(needle)
    while i >= 0 and len(out) < limit:
        out.append(i)
        i = hay.find(needle, i + 1)
    return out


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
            full = np.vstack([top, bot])
            ink = int(((full == 11) | (full == 12)).sum())
            if 4 <= ink <= 120:
                gs.append({"m": full, "r": r, "c": c, "ink": ink})
    print(f"真实 8x16 字形：{len(gs)}")

    # 归一化矩阵
    for g in gs:
        m = g["m"]
        n = np.zeros_like(m)
        n[m == 10] = 0
        n[m == 11] = 1
        n[m == 12] = 2
        g["n"] = n

    # ── 编码矩阵 ─────────────────────────────────────────
    ENC: dict[str, callable] = {
        "2bpp-M": lambda g: enc_2bpp(g["n"], True),
        "2bpp-L": lambda g: enc_2bpp(g["n"], False),
        "4bpp-64": lambda g: enc_4bpp(g["n"]),
        "1bpp-core-M": lambda g: enc_1bpp((g["m"] == 12).astype(np.uint8), True),
        "1bpp-core-L": lambda g: enc_1bpp((g["m"] == 12).astype(np.uint8), False),
        "1bpp-any-M": lambda g: enc_1bpp(((g["m"] == 11) | (g["m"] == 12)).astype(np.uint8), True),
        "1bpp-any-L": lambda g: enc_1bpp(((g["m"] == 11) | (g["m"] == 12)).astype(np.uint8), False),
        "planar": lambda g: enc_planar((g["m"] == 12).astype(np.uint8)),
    }

    best_overall = None
    summary = {}

    for rname, (base, path) in RAM.items():
        if not path.exists():
            continue
        hay = path.read_bytes()
        print("\n" + "=" * 78)
        print(f"搜索 {rname}  0x{base:08X}  {len(hay):,} B")
        print("=" * 78)
        summary[rname] = {}
        for ename, fn in ENC.items():
            hits = 0
            offs = []
            for g in gs:
                pat = fn(g)
                loc = find_all(hay, pat, limit=64)
                if loc:
                    hits += 1
                    offs.extend(loc)
            summary[rname][ename] = {"hits": hits, "offs": sorted(set(offs))[:64]}
            if hits == 0:
                continue
            so = sorted(set(offs))
            gaps = [b - a for a, b in zip(so, so[1:])]
            gc = Counter(gaps)
            gtop = gc.most_common(1)[0] if gc else (0, 0)
            line = (f"  {ename:<12} 命中字 {hits:>3}/{len(gs)}  "
                    f"位置 {len(so):>3}  最多间隔 {gtop[0]}x{gtop[1]}")
            print(line)
            if gtop[1] >= 4 and 8 <= gtop[0] <= 512:
                print(f"    ★★★ 等距表候选！stride={gtop[0]}B  "
                      f"地址 {[hex(base + x) for x in so[:10]]}")
                if best_overall is None or hits > best_overall["hits"]:
                    best_overall = {"ram": rname, "enc": ename,
                                    "hits": hits, "stride": gtop[0],
                                    "addrs": [base + x for x in so[:64]]}

    print("\n" + "=" * 78)
    print("结论")
    print("=" * 78)
    if best_overall:
        print(f"  ★ 字库候选：{best_overall['ram']} / {best_overall['enc']}")
        print(f"    stride={best_overall['stride']}B  "
              f"命中 {best_overall['hits']}/{len(gs)}")
        print(f"    地址：{[hex(a) for a in best_overall['addrs'][:20]]}")
    else:
        print("  ✘ RAM 里也没有等距的 8x16 字形表")
        print("  ⇒ 字形是「逐字实时绘制」的，不是整表查表")
        print("     （即 ROM 里存的是笔画/组件描述，不是点阵）")

    (OUT / "ram_search.json").write_text(
        json.dumps({"n_glyphs": len(gs), "summary": summary,
                    "best": best_overall}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"\n已写 {OUT / 'ram_search.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
