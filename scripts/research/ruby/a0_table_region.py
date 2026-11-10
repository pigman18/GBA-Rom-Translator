#!/usr/bin/env python3
"""A0.2 定性：剧情 1,103 条的指针站点在「表区 0x1C0000-0x400000」是什么？

这不是随机分布 —— 1065/1208 的指针站点都落在同一个 2.4MB 区间，
说明这些条目大概率是「被指针表引用的文本」，而不是自由剧情文本。

待查：
  1. 这些条目的指针站点是否成规律（等距/成组）
  2. 它们指向的文本是否也是成组的
  3. 是否是某种「文本指针表」

用法：
    python scripts/research/ruby/a0_table_region.py
"""
from __future__ import annotations

import json
import struct
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
GBA_BASE = 0x08000000


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = d.get("entries") or []

    from meowth.policy import collect_entry_text_spans, ptr_site_in_text_body
    text_spans = collect_entry_text_spans(entries)

    f980 = [e for e in entries
            if e.get("type") == "replace" and e.get("phrase_code") is not None
            and (e.get("module") or "") == "剧情"]

    idx: dict[int, list[int]] = {}
    for off in range(0, len(rom) - 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            idx.setdefault(v - GBA_BASE, []).append(off)

    targets = []   # (entry, usable_sites)
    for e in f980:
        a = e.get("address") or "0x0"
        try:
            addr = int(str(a).replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        sites = [s for s in (idx.get(addr) or []) if not (s & 3)]
        usable = [s for s in sites if not ptr_site_in_text_body(s, text_spans)]
        if usable:
            targets.append((e, addr, usable))

    print(f"剧情里「有可用对齐指针」的 F980 条目: {len(targets):,}\n")

    # 1. 指针站点分布：是否成组（连续 4 字节间隔）
    site_all = []
    for _e, _addr, sites in targets:
        site_all.extend(sites[:1])
    site_all.sort()
    gaps = Counter()
    for a, b in zip(site_all, site_all[1:]):
        gaps[b - a] += 1
    print("=== 指针站点之间的间距分布（前 10）===")
    for g, c in gaps.most_common(10):
        print(f"  间距 {g:>6} 字节: {c:>4} 次")
    print()

    # 2. 目标文本地址分布
    tgt_all = sorted(t[1] for t in targets)
    print("=== 目标文本地址范围 ===")
    print(f"  最小 0x{min(tgt_all):06X}  最大 0x{max(tgt_all):06X}")
    tg = Counter()
    for a, b in zip(tgt_all, tgt_all[1:]):
        tg[b - a] += 1
    print("  相邻目标间距（前 8）:")
    for g, c in tg.most_common(8):
        print(f"    {g:>6} 字节: {c:>4} 次")
    print()

    # 3. 样本：看指针站点和目标的对应
    print("=== 样本（前 12）===")
    for e, addr, sites in targets[:12]:
        s = sites[0]
        print(f"  文本 0x{addr:06X} ← 指针站点 0x{s:X}")
        print(f"    原文: {(e.get('original') or '')[:46]!r}")
        # 站点附近的 u32 序列
        ctx = []
        for k in range(-2, 3):
            p = s + k * 4
            if 0 <= p < len(rom) - 4:
                v = struct.unpack_from("<I", rom, p)[0]
                t = v - GBA_BASE if GBA_BASE <= v < 0x0A000000 else None
                ctx.append(f"{k:+d}:0x{t:06X}" if t else f"{k:+d}:0x{v:08X}")
        print(f"    站点邻域: {'  '.join(ctx)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
