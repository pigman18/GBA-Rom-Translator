#!/usr/bin/env python3
"""定位火红原版物种名表，验证它是否被改动。

已知：汉化把代码里 31 处引用改成指向 0x0871F444 的新中文表。
待确认：原版日文物种名表在哪，汉化有没有动它。

火红/口袋妖怪 GBA 的 gSpeciesNames 通常是 412 项 × 11 字节。
本脚本用「假名密度 + FF 结尾 + 项数」扫原版，再比对汉化同区。

用法：
    python scripts/research/firered/probe_orig_species.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ORIG = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"


def is_kana(b: int) -> bool:
    return 0x01 <= b <= 0x60


def score_table(buf: bytes, base: int, stride: int, n: int) -> tuple[float, int]:
    """打分：每项末字节是 FF 且项内假名密度高的比例。"""
    ok = 0
    nonempty = 0
    for k in range(n):
        off = base + k * stride
        if off + stride > len(buf):
            break
        seg = buf[off:off + stride]
        if seg[-1] != 0xFF:
            continue
        body = seg[:-1]
        if not body:
            continue
        nonempty += 1
        kana = sum(1 for b in body if is_kana(b))
        if kana / len(body) > 0.8:
            ok += 1
    return (ok / nonempty if nonempty else 0.0), nonempty


def main() -> int:
    a = ORIG.read_bytes()
    b = ZH.read_bytes()
    print(f"origin/zh 各 {len(a):,} B\n")

    print("=== 扫原版找 412 项 × 11B 的日文名表 ===")
    best = []
    for base in range(0x300000, 0x800000, 4):
        r, ne = score_table(a, base, 11, 60)
        if r > 0.9 and ne >= 50:
            best.append((base, r, ne))
    print(f"  命中 {len(best)} 处（前 6）:")
    for base, r, ne in best[:6]:
        d = sum(1 for x, y in zip(a[base:base + 11 * 60], b[base:base + 11 * 60]) if x != y)
        span = 11 * 60
        print(f"    0x{base:06X}  合规 {r:.0%} ({ne} 非空项)  汉化差异 {d}/{span} ({d/span:.0%})")
        print(f"      原版: {a[base:base+33].hex(' ')}")
        print(f"      汉化: {b[base:base+33].hex(' ')}")

    print()
    print("=== 该表在汉化版是否被代码字面量引用（判断是否还在用）===")
    import struct
    GBA_BASE = 0x08000000
    for base, _r, _ne in best[:3]:
        needle = struct.pack("<I", base + GBA_BASE)
        ra = a.count(needle)
        rb = b.count(needle)
        print(f"  0x{base:06X}: 原版引用 {ra} 处 → 汉化 {rb} 处")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
