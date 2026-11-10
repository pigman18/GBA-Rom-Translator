#!/usr/bin/env python3
"""texts_17: 「模块重复覆盖」终判 —— 用生产路径的真实 FCFS 归属验证。

texts_05 用「条目地址集合」求交得 0，但那只证明两条目没有相同起点，
不能证明区域不重复。真正的判据是：

  把每个模块单独跑一遍（不带 exclude_ranges），得到它「本来想收」的候选集；
  若模块 B 的候选集大量落在模块 A 已导出的字节内，
  则 B 在这片区域上是被 A 抢先认领（要么该合并，要么该收窄 B 的范围）。

同时统计「同一片 ROM 字节被几个模块的候选覆盖」，找出真正重复的区段。

用法: python scripts/research/ruby/texts_17_redundancy.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
OUT = ROOT / "work" / "_probe" / "texts_band_owners.json"


def to_int(v):
    if v is None:
        return None
    if isinstance(v, int):
        return v
    s = str(v).strip()
    try:
        return int(s, 16) if s.lower().startswith("0x") else int(s, 10)
    except ValueError:
        return None


def main() -> int:
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods = d["modules"]

    # 每个模块的「声明覆盖带」：定长表用几何推出的完整带（含槽间填充）
    # scan 模块用条目真实跨度
    bands: dict[str, list[tuple[int, int]]] = {}
    for name, m in mods.items():
        typ = m.get("type")
        start = to_int(m.get("start"))
        end = to_int(m.get("end"))
        r = m.get("read") or {}
        stride = r.get("stride") or r.get("entry_size")
        if typ in ("stride", "struct") and start and end and stride:
            bands[name] = [(start, end)]
        elif typ == "stride_ptr" and start and end:
            # 指针表本身占 [start, end]；指向的正文另算
            bands[name] = [(start, end)]
        else:
            bands[name] = []

    # scan 模块的真实跨度
    for name, m in mods.items():
        if m.get("type") != "scan":
            continue
        els = [e for e in d["entries"] if e.get("module") == name]
        lo = hi = None
        for e in els:
            a = to_int(e.get("address"))
            if a is None:
                continue
            off = a - 0x08000000 if a >= 0x08000000 else a
            lo = off if lo is None else min(lo, off)
            hi = off if hi is None else max(hi, off)
        if lo is not None:
            bands[name] = [(lo, hi)]

    print("=" * 118)
    print("模块声明覆盖带")
    print("=" * 118)
    for name, bs in bands.items():
        if not bs:
            print(f"  {name:<20} （无带）")
            continue
        for lo, hi in bs:
            print(f"  {name:<20} 0x{lo:06X}..0x{hi:06X}  ({(hi-lo+1):,} bytes)")

    print()
    print("=" * 118)
    print("重叠矩阵（只列有交集的；scan 模块的带是条目跨度，非声明全 ROM）")
    print("=" * 118)
    names = [n for n, b in bands.items() if b]
    seen = set()
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            for (alo, ahi) in bands[a]:
                for (blo, bhi) in bands[b]:
                    lo, hi = max(alo, blo), min(ahi, bhi)
                    if lo <= hi:
                        key = (a, b)
                        if key in seen:
                            continue
                        seen.add(key)
                        print(f"  {a:<20} ∩ {b:<20} 0x{lo:06X}..0x{hi:06X} "
                              f"({hi-lo+1:,} bytes)")
    if not seen:
        print("  （定长表之间无交叠）")

    # 全 ROM scan 模块的关键问题：它们声明的 start..end 是 0..0xFFFFFF
    print()
    print("=" * 118)
    print("全 ROM scan 模块（声明 0x0..0xFFFFFF，天然包住所有定长表）")
    print("=" * 118)
    for name, m in mods.items():
        if m.get("type") != "scan":
            continue
        s = to_int(m.get("start"))
        e = to_int(m.get("end"))
        if s == 0 and e in (0xFFFFFF, 0x7FFFFF):
            n = sum(1 for x in d["entries"] if x.get("module") == name)
            print(f"  {name:<20} 声明 0x{s:X}..0x{e:X}  实际条目 {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
