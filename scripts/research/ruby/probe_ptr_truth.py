#!/usr/bin/env python3
"""实测：被判「无指针」的 F980 条目，ROM 里到底有没有指针指向它们。

背景：
  translate_plan.resolve_usable_pointers() 只在 entry 已登记指针时做校验：
      raw = list(_ptr_sources(entry))
      if not raw: return []          ← 没登记 = 直接判无指针，不搜 ROM
  所以「7,144 条 pointer_sources = 0」只是 extract 没登记，
  不代表 ROM 里没有指针。

本脚本绕过 extract，直接扫全 ROM 找指向这些条目地址的 u32（含非对齐）。

用法：
    python scripts/research/ruby/probe_ptr_truth.py
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
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"

GBA_BASE = 0x08000000


def build_ptr_index(rom: bytes) -> dict[int, list[int]]:
    """全 ROM 扫 u32（4 对齐 + 非对齐都扫），建立 target_off → [来源偏移]。"""
    idx: dict[int, list[int]] = {}
    n = len(rom) - 4
    for off in range(0, n):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            t = v - GBA_BASE
            idx.setdefault(t, []).append(off)
    return idx


def main() -> int:
    rom = ROM.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = d.get("entries") or []

    print("建立全 ROM 指针索引（含非对齐）…")
    idx = build_ptr_index(rom)
    print(f"  唯一目标地址 {len(idx):,} 个\n")

    f980 = [e for e in entries
            if e.get("type") == "replace" and e.get("phrase_code") is not None]
    print(f"F980 条目 {len(f980):,}\n")

    has_ptr = 0
    no_ptr = []
    by_mod_hit: Counter = Counter()
    by_mod_miss: Counter = Counter()

    for e in f980:
        a = e.get("address") or ""
        try:
            addr = int(str(a).replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        sites = idx.get(addr)
        if sites:
            has_ptr += 1
            by_mod_hit[e.get("module")] += 1
        else:
            no_ptr.append(e)
            by_mod_miss[e.get("module")] += 1

    total = has_ptr + len(no_ptr)
    print("=== 绕过 extract，直接扫 ROM 的结果 ===")
    print(f"  有指针指向正文起点: {has_ptr:,} ({has_ptr/total:.1%})")
    print(f"  确实找不到指针:     {len(no_ptr):,} ({len(no_ptr)/total:.1%})")
    print()

    print("=== 按模块（有指针 / 无指针）===")
    mods = sorted(set(by_mod_hit) | set(by_mod_miss),
                  key=lambda m: -(by_mod_hit[m] + by_mod_miss[m]))
    print(f"  {'模块':<18} {'有指针':>6} {'无指针':>6}")
    for m in mods:
        print(f"  {m:<18} {by_mod_hit[m]:>6} {by_mod_miss[m]:>6}")

    print()
    print("=== 无指针样本（看这些是什么）===")
    for e in no_ptr[:10]:
        print(f"  {e.get('module')} {e.get('address')} bl={e.get('byte_length')}")
        print(f"    original: {(e.get('original') or '')[:60]!r}")

    out = ROOT / "work" / "_probe" / "ruby_ptr_truth.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "has_ptr": has_ptr,
        "no_ptr": len(no_ptr),
        "by_mod_hit": dict(by_mod_hit),
        "by_mod_miss": dict(by_mod_miss),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
