#!/usr/bin/env python3
"""调研(173) 用 VRAM 里的**原始 tile**（不是按 13px 重切的）去搜 ROM。

═══════════════════════════════════════════════════════════════════════════
【我之前的根本错误】
═══════════════════════════════════════════════════════════════════════════
汉字步进 13px，而 tile 是 8px，两者**不对齐**。

所以 tilemap 里 tile 1 的内容不是「某个字的左上角」，
而是「第 0 个字的后半 + 第 1 个字的前半」这类混合碎片。

我之前按 13px 从 VRAM 像素重切出「干净的字形」，
拿这些**渲染结果**去 ROM 搜——当然搜不到，因为 ROM 里存的是字库，
不是渲染输出。

【正确做法：直接拿 VRAM 的原始 tile 字节】
VRAM tile 1、2（第 1 行左、右）+ tile 25、26（第 2 行左、右）
= 4 × 32 = 128 字节，这就是**一个 16×16 的字符格**。

这才是和 ROM 字库可比对的最小单位。

【本脚本】
 ① 从 VRAM 原样取出 tile 1/2/25/26 等组合（多种排列）
 ② 三种归一化：原样 / 10→0,11→1,12→2 / 12→1 其余 0
 ③ 每种都去 ROM 搜（128B、64B、32B 三种长度）
 ④ 报告命中与聚集

用法：python scripts/research/firered/173_raw_tiles.py
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


def norm_map(blob: bytes, mode: str) -> bytes:
    out = bytearray()
    for b in blob:
        hi, lo = b >> 4, b & 0x0F
        if mode == "raw":
            out.append(b)
            continue
        def f(v: int) -> int:
            if mode == "012":
                return {10: 0, 11: 1, 12: 2}.get(v, 0)
            if mode == "01":
                return 1 if v == 12 else 0
            if mode == "0123":
                return {10: 0, 11: 1, 12: 2, 0: 0}.get(v, 0)
            return v
        out.append((f(hi) << 4) | f(lo))
    return bytes(out)


def main() -> int:
    vr = (SNAP / "vram.bin").read_bytes()
    zh = FR_ZH.read_bytes()
    ja = FR_JA.read_bytes()

    def tile(i: int) -> bytes:
        return vr[i * 32:(i + 1) * 32]

    # tilemap 行1 = tiles 1..7，行2 = tiles 25..31
    # 所以前两个字用 tile 1,2 (上) 和 25,26 (下)
    combos = {
        "上[1,2]+下[25,26]": tile(1) + tile(2) + tile(25) + tile(26),
        "上[1,2]+下[25,26] 交替": tile(1) + tile(25) + tile(2) + tile(26),
        "仅上[1,2]": tile(1) + tile(2),
        "仅上[1]": tile(1),
        "上[2,3]+下[26,27]": tile(2) + tile(3) + tile(26) + tile(27),
        "仅上[2]": tile(2),
    }

    print("=" * 78)
    print("① VRAM 原始 tile 内容")
    print("=" * 78)
    for i in (1, 2, 25, 26):
        b = tile(i)
        u = sorted(set(v for x in b for v in (x & 0xF, x >> 4)))
        print(f"  tile {i:>2}: {b[:16].hex(' ')}  nibble={u}")

    for mode in ("raw", "012", "01", "0123"):
        print("\n" + "=" * 78)
        print(f"② 归一化模式 = {mode}")
        print("=" * 78)
        for cname, cblob in combos.items():
            pat = norm_map(cblob, mode)
            core = pat
            # 去掉长串相同字节（全 0 或全 1）避免假命中
            if len(set(core)) <= 1:
                continue
            hits = []
            i = zh.find(core)
            while i >= 0 and len(hits) < 40:
                hits.append(i)
                i = zh.find(core, i + 1)
            if hits:
                same = sum(1 for h in hits if ja[h:h + len(core)] == core)
                print(f"  {cname:<26} 命中 {len(hits):>3}  "
                      f"（原版相同 {same}）")
                z = Counter(h // 0x10000 for h in hits)
                top = ", ".join(f"0x{BASE+k*0x10000:08X}:{v}"
                                for k, v in z.most_common(3))
                print(f"      分布: {top}")

    # ── ③ 用 16 字节短片段（更宽松）──────────────────
    print("\n" + "=" * 78)
    print("③ 短片段搜索（每个 tile 的后 16 字节，容忍前缀不同）")
    print("=" * 78)
    for i in (1, 2, 3, 25, 26, 27):
        for mode in ("012", "01"):
            pat = norm_map(tile(i)[16:32], mode)
            if len(set(pat)) <= 1:
                continue
            hits = []
            j = zh.find(pat)
            while j >= 0 and len(hits) < 30:
                hits.append(j)
                j = zh.find(pat, j + 1)
            if hits:
                print(f"  tile{i} 后半 [{mode}] 命中 {len(hits)}")
                z = Counter(h // 0x10000 for h in hits)
                for k, v in z.most_common(3):
                    print(f"      0x{BASE+k*0x10000:08X}: {v}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
