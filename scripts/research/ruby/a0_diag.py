#!/usr/bin/env python3
"""A0 诊断：4,500 条「有指针但没登记」到底卡在哪一步。

已知 resolve_usable_pointers() 只在 entry 已登记指针时才校验：
    raw = list(_ptr_sources(entry))
    if not raw: return []          ← 没登记 = 直接判无指针
所以问题出在 extract 阶段没登记。

本脚本对每个 F980 条目：
  1. 扫 ROM 找指向它的 u32（已知 4,500 条有）
  2. 逐一检查这些指针站点是否会被 filter 挡掉：
     - 非 4 字节对齐
     - 落在 text_spans（正文体内）
     - 落在 title_gfx_ptr_deny / TITLE_LZ_BAND
  3. 输出「第一道挡住它的过滤器」统计

用法：
    python scripts/research/ruby/a0_diag.py
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

    # 引入真实过滤器判定
    from meowth.policy import (
        collect_entry_text_spans,
        title_gfx_ptr_deny,
        TITLE_LZ_BAND,
        ptr_site_in_text_body,
    )

    text_spans = collect_entry_text_spans(entries)
    print(f"条目 {len(entries):,}，正文体 text_spans {len(text_spans):,} 段")

    deny = title_gfx_ptr_deny()
    tlz = TITLE_LZ_BAND()
    print(f"title_gfx_ptr_deny: {list(deny)[:3]}…" if deny else "title_gfx_ptr_deny: 空")
    print(f"TITLE_LZ_BAND: 0x{tlz[0]:X}..0x{tlz[1]:X}\n")

    f980 = [e for e in entries
            if e.get("type") == "replace" and e.get("phrase_code") is not None]

    # 建索引：目标 → 指针来源
    idx: dict[int, list[int]] = {}
    for off in range(0, len(rom) - 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            idx.setdefault(v - GBA_BASE, []).append(off)

    stats: Counter = Counter()
    n_have_ptr = 0

    for e in f980:
        a = e.get("address") or "0x0"
        try:
            addr = int(str(a).replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        sites = idx.get(addr)
        if not sites:
            stats["真无指针"] += 1
            continue
        n_have_ptr += 1

        # 逐一判定每个站点能否通过
        usable = 0
        reasons = []
        for s in sites:
            if s & 3:
                reasons.append("非4对齐")
                continue
            if ptr_site_in_text_body(s, text_spans):
                reasons.append("落正文体")
                continue
            if s in deny:
                reasons.append("标题图形指针")
                continue
            if tlz[0] <= s < tlz[1]:
                reasons.append("标题LZ带")
                continue
            usable += 1

        if usable:
            stats["有可用指针"] += 1
        else:
            # 记第一道拦截原因
            stats[f"全被挡:{reasons[0] if reasons else '未知'}"] += 1

    print("=== 分析结果 ===")
    print(f"  有指针指向的 F980: {n_have_ptr:,}")
    for k, v in stats.most_common():
        print(f"    {k:<22} {v:>6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
