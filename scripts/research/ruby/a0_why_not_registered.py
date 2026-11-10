#!/usr/bin/env python3
"""A0.2：1,719 条「有对齐指针」为什么没被 extract 登记？

已知：
  - F980 里 1,719 条有 4 对齐指针（理论上能 relocate）
  - 但 build.json 里它们的 pointer_sources = 0
  - resolve_usable_pointers() 只在 entry 已登记时校验，没登记直接返回 []

所以要在 extract 阶段找原因。逐个检查：
  1. 该条目的 module 是否 relocate:false（模块开关挡住）
  2. 该条目是否根本没带 pointer_addresses 字段
  3. 指针站点是否被某个 filter 拒（落正文体/标题区等）

用法：
    python scripts/research/ruby/a0_why_not_registered.py
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
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
GBA_BASE = 0x08000000


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = d.get("entries") or []
    mods = (json.loads(TEXTS.read_text(encoding="utf-8")).get("modules") or {})

    from meowth.policy import collect_entry_text_spans, ptr_site_in_text_body

    text_spans = collect_entry_text_spans(entries)

    f980 = [e for e in entries
            if e.get("type") == "replace" and e.get("phrase_code") is not None]

    idx: dict[int, list[int]] = {}
    for off in range(0, len(rom) - 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            idx.setdefault(v - GBA_BASE, []).append(off)

    stats: Counter = Counter()
    mod_stats: Counter = Counter()
    samples = []

    for e in f980:
        a = e.get("address") or "0x0"
        try:
            addr = int(str(a).replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        sites = idx.get(addr) or []
        aligned = [s for s in sites if not (s & 3)]
        if not aligned:
            continue   # 只看有对齐指针的 1,719 条

        mod = e.get("module") or ""
        meta = mods.get(mod) or {}
        w = meta.get("write") or {}
        reloc = w.get("relocate", True)
        typ = meta.get("type") or "?"

        # 逐项判定
        usable = []
        blocked = []
        for s in aligned:
            if ptr_site_in_text_body(s, text_spans):
                blocked.append("落正文体")
            else:
                usable.append(s)

        if not reloc:
            stats["模块 relocate:false"] += 1
            mod_stats[mod] += 1
        elif usable:
            stats["应可 relocate 但未登记"] += 1
            mod_stats[mod] += 1
            if len(samples) < 12:
                samples.append((e, usable, typ, reloc))
        else:
            stats[f"全被 filter 挡: {blocked[0] if blocked else '?'}"] += 1

    print("=== 1,719 条「有对齐指针」的登记失败原因 ===")
    for k, v in stats.most_common():
        print(f"  {k:<28} {v:>6}")
    print()

    print("=== 按模块分布（前 12）===")
    for m, c in mod_stats.most_common(12):
        meta = mods.get(m) or {}
        w = meta.get("write") or {}
        print(f"  {m:<20} {c:>5}  type={meta.get('type','?'):<11} "
              f"relocate={w.get('relocate','(默认true)')}")
    print()

    print("=== 应可 relocate 但没登记的样本 ===")
    for e, usable, typ, reloc in samples:
        print(f"  {e.get('module')} {e.get('address')} bl={e.get('byte_length')} "
              f"type={typ} relocate={reloc}")
        print(f"    可用指针站点: " + ", ".join(f"0x{s:X}" for s in usable[:4]))
        print(f"    原文: {(e.get('original') or '')[:50]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
