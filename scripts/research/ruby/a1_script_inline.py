#!/usr/bin/env python3
"""A1 最后一环：4,180 条无指针文本，靠什么被引用？

已排除：
  - 直接指针（0 命中）
  - 块首指针（0/1759）
  - 偏移 ±4 内（仅 90 条）

剩下最大可能：**脚本 VM 的 message/trainerbattle op 内联**
火红做法是 02 67 <ptr> 形态（opcode + 对齐的指针）。

本脚本：扫描全 ROM，找「opcode + 指向文本区的 u32」的脚本形态，
看能否覆盖这 4,180 条。

ruby 脚本 opcode 常见值（pokeruby script.h）：
  0x02 = end
  0x03 = nop
  0x04 = nop1
  0x05 = ...
  0x66 = msgbox / message 类
  0x67 = message
  0x68 = ...

更稳的做法：直接扫「u32 落在文本区 0x140000-0x1C0000 的所有位置」，
不管对齐，统计能覆盖多少 NO_PTR 条目。

用法：
    python scripts/research/ruby/a1_script_inline.py
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
OWN = ROOT / "work" / "_probe" / "a1_ownership.json"
GBA_BASE = 0x08000000


def main() -> int:
    rom = ROM_PATH.read_bytes()
    own = json.loads(OWN.read_text(encoding="utf-8"))
    no_ptr = own.get("NO_PTR") or []
    targets = {int(r["addr"].replace("0x", ""), 16) for r in no_ptr}
    print(f"NO_PTR 条目 {len(targets):,}\n")

    # 扫全 ROM 所有 4 字节窗口（含非对齐），记录 → 目标
    all_refs: dict[int, list[int]] = {}
    n = len(rom) - 4
    for off in range(0, n):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            t = v - GBA_BASE
            if t in targets:
                all_refs.setdefault(t, []).append(off)

    covered = len(all_refs)
    print("=== 任意对齐位置引用（含非对齐）===")
    print(f"  被引用的 NO_PTR 条目: {covered:,} / {len(targets):,} "
          f"({covered/len(targets):.1%})")

    # 按引用位置是否 4 对齐分
    al = un = 0
    for t, offs in all_refs.items():
        for o in offs:
            if o & 3:
                un += 1
            else:
                al += 1
    print(f"  引用位置 4 对齐: {al:,}")
    print(f"  引用位置非对齐:  {un:,}")
    print()

    # 检查引用位置的上下文：前面一字节是什么（判断是否 opcode）
    prev_bytes: Counter = Counter()
    for t, offs in list(all_refs.items()):
        for o in offs[:1]:
            if o > 0:
                prev_bytes[rom[o - 1]] += 1

    print("=== 引用位置前一字节分布（前 15）===")
    for b, c in prev_bytes.most_common(15):
        print(f"  0x{b:02X}: {c}")

    # 完全没被任何位置引用的
    uncovered = targets - set(all_refs)
    print()
    print(f"=== 完全无任何引用（任意对齐）的条目: {len(uncovered):,} ===")
    if uncovered:
        sample = sorted(uncovered)[:8]
        print("  样本地址: " + ", ".join(f"0x{a:06X}" for a in sample))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
