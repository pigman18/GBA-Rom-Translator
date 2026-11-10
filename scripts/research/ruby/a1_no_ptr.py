#!/usr/bin/env python3
"""A1 深挖：NO_PTR 4,270 条里，剧情 3,845 条到底是什么。

A1 初步分类结果：
  FIXED_TABLE   1,178  ← 定长表，好办
  PTR_ARRAY     1,034  ← 指针数组，整表搬
  CODE_LITERAL    298  ← 字面量池，逐条改
  FREE_TEXT       259  ← 自由文本，relocate
  NO_PTR_BLOCKED  105  ← 被 filter 挡
  NO_PTR        4,270  ← 其中剧情 3,845

待查：剧情 3,845 条真的无指针？还是别名/子串导致？

怀疑点：
  A. 它们是长文本中间部分（extract 把一段切成多条）
  B. 它们地址前移了几字节（FD 回退 / rebase）
  C. 真的无指针

判据：
  检查 addr-1、addr-2、addr-3 是否被指针引用（FD 回退后地址可能偏移）

用法：
    python scripts/research/ruby/a1_no_ptr.py
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
    own = json.loads(OWN.read_text(encoding="utf-8"))

    no_ptr = own.get("NO_PTR") or []
    print(f"NO_PTR 条目: {len(no_ptr):,}\n")

    # 全 ROM 指针索引（4 对齐）
    idx: dict[int, list[int]] = {}
    for off in range(0, len(rom) - 4, 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            idx.setdefault(v - GBA_BASE, []).append(off)

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

    stats: Counter = Counter()
    samples = []

    for rec in no_ptr:
        addr = int(rec["addr"].replace("0x", ""), 16)
        # 检查附近偏移是否有指针
        found_at = None
        for delta in range(-4, 5):
            if addr + delta in idx:
                found_at = delta
                break
        if found_at is not None:
            stats[f"附近±{found_at:+d}有指针"] += 1
        else:
            stats["5 字节内全无指针"] += 1

        # 检查是否是长串的中间（前一个字节不是 FF，说明前面还有内容）
        prev = rom[addr - 1] if addr > 0 else 0
        if prev != 0xFF:
            stats["前一字节非FF（可能是长串中部）"] += 1

        if len(samples) < 10 and found_at is not None:
            e = by_addr.get(addr)
            samples.append((rec, found_at, e))

    print("=== 剧情 NO_PTR 的偏移检查 ===")
    for k, v in stats.most_common():
        print(f"  {k:<30} {v:>5}")
    print()

    print("=== 附近有指针的样本 ===")
    for rec, delta, e in samples:
        addr = int(rec["addr"].replace("0x", ""), 16)
        sites = idx.get(addr + delta, [])
        print(f"  {rec['addr']} (Δ{delta:+d}) 指针 {len(sites)} 处"
              + (f": {', '.join(f'0x{s:X}' for s in sites[:3])}" if sites else ""))
        if e:
            print(f"    原文: {(e.get('original') or '')[:50]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
