#!/usr/bin/env python3
"""A1 收尾：1,490 条「真无任何引用」的文本是什么？

样本: 0x14A94C, 0x14A983, 0x14A9D5, 0x14A9F6, 0x14AA79...

判据：
  A. 是长串被切开的片段（前一条目不以其结尾 FF 收尾）
  B. 前一字节不是 FF → 说明它在某个长串中部
  C. 真的孤立（需缩句）

用法：
    python scripts/research/ruby/a1_uncovered.py
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
OWN = ROOT / "work" / "_probe" / "a1_ownership.json"
GBA_BASE = 0x08000000


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = d.get("entries") or []
    by_addr = {}
    for e in entries:
        a = e.get("address") or ""
        try:
            addr = int(str(a).replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        by_addr[addr] = e

    own = json.loads(OWN.read_text(encoding="utf-8"))
    targets = {int(r["addr"].replace("0x", ""), 16) for r in (own.get("NO_PTR") or [])}

    # 找任意对齐引用
    covered = set()
    n = len(rom) - 4
    for off in range(0, n):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            t = v - GBA_BASE
            if t in targets:
                covered.add(t)

    uncovered = sorted(targets - covered)
    print(f"NO_PTR {len(targets):,}，有引用 {len(covered):,}，"
          f"无任何引用 {len(uncovered):,}\n")

    # 分析无引用条目
    stats: Counter = Counter()
    samples = []
    for a in uncovered:
        prev = rom[a - 1] if a > 0 else 0
        e = by_addr.get(a)
        raw = b""
        if e:
            try:
                raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
            except ValueError:
                pass

        if prev != 0xFF:
            stats["前一字节非 FF（长串中部）"] += 1
        else:
            stats["前一字节是 FF（独立串）"] += 1

        # 前面紧邻是否有另一个条目（可能是同一长串被切开）
        is_concat = False
        for delta in (1, 2, 3):
            if a - delta in by_addr:
                is_concat = True
                break
        if is_concat:
            stats["紧邻前一条目（疑似切开）"] += 1

        if len(samples) < 12:
            samples.append((a, prev, e, raw))

    print("=== 1,490 条的形态 ===")
    for k, v in stats.most_common():
        print(f"  {k:<28} {v:>5}")
    print()

    print("=== 样本 ===")
    for a, prev, e, raw in samples:
        print(f"  0x{a:06X} 前字节 0x{prev:02X}  len={len(raw)}")
        if e:
            print(f"    原文: {(e.get('original') or '')[:56]!r}")
            print(f"    hex : {raw[:40].hex(' ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
