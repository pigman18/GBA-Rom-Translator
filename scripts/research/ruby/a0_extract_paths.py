#!/usr/bin/env python3
"""A0.2 深查：1,208 条「应可 relocate 但未登记」卡在 extract 哪一步。

已知：这些条目 ROM 里有 4 对齐指针指向它们，模块也没禁 relocate，
但 extract 生成的 entry 里没有 pointer_addresses/pointer_sources。

下一步：查 extract.py 里各条路径是否登记指针。
重点看「模块 type 决定走哪个分支」。

用法：
    python scripts/research/ruby/a0_extract_paths.py
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

    # 1,208 条按模块 × type 细分
    by_mod: Counter = Counter()
    by_type: Counter = Counter()
    # 指针站点在哪个区域（代码段 / 数据区 / 表区）
    site_zone: Counter = Counter()

    for e in f980:
        a = e.get("address") or "0x0"
        try:
            addr = int(str(a).replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        sites = [s for s in (idx.get(addr) or []) if not (s & 3)]
        if not sites:
            continue
        mod = e.get("module") or ""
        meta = mods.get(mod) or {}
        w = meta.get("write") or {}
        if not w.get("relocate", True):
            continue
        usable = [s for s in sites if not ptr_site_in_text_body(s, text_spans)]
        if not usable:
            continue

        by_mod[mod] += 1
        by_type[meta.get("type") or "?"] += 1
        for s in usable:
            if s < 0x10000:
                site_zone["代码段早期 <0x10000"] += 1
            elif s < 0x100000:
                site_zone["代码段 0x10000-0x100000"] += 1
            elif s < 0x1C0000:
                site_zone["数据区 0x100000-0x1C0000"] += 1
            elif s < 0x400000:
                site_zone["表区 0x1C0000-0x400000"] += 1
            else:
                site_zone["高地址 >=0x400000"] += 1
            break

    print("=== 1,208 条按模块 ===")
    for m, c in by_mod.most_common(15):
        print(f"  {m:<20} {c:>5}")
    print()

    print("=== 按模块 type ===")
    for t, c in by_type.most_common():
        print(f"  {t:<14} {c:>5}")
    print()

    print("=== 指针站点所在区域 ===")
    for z, c in site_zone.most_common():
        print(f"  {z:<26} {c:>5}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
