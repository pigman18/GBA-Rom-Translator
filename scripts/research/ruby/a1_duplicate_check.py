#!/usr/bin/env python3
"""A1.4 终局判据：919 条零引用文本，用「重复内容」检测无效数据。

关键洞察：
  若一段文本在 ROM 里**重复出现多次**，而其中一份有引用、另一份没有，
  那没引用的那份就是死数据（开发残留）。

另外检验：
  - 这些文本是否与「有引用的文本」内容重复
  - 重复率多高

用法：
    python scripts/research/ruby/a1_duplicate_check.py
"""
from __future__ import annotations

import json
import struct
import sys
from collections import Counter, defaultdict
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

    addr_to_entry = {}
    for e in entries:
        a = e.get("address") or ""
        try:
            addr = int(str(a).replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        addr_to_entry[addr] = e

    own = json.loads(OWN.read_text(encoding="utf-8"))
    targets = {int(r["addr"].replace("0x", ""), 16) for r in (own.get("NO_PTR") or [])}

    ref_targets: set[int] = set()
    for off in range(0, len(rom) - 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            ref_targets.add(v - GBA_BASE)

    zero = sorted(t for t in targets if t not in ref_targets and t > 0 and rom[t-1] == 0xFF)
    print(f"零引用独立串: {len(zero):,}\n")

    # 1. 内容重复检测：同样的 hex 在 ROM 里出现几次
    dup_in_rom = 0
    dup_with_ref = 0
    samples = []
    for a in zero:
        e = addr_to_entry.get(a)
        if not e:
            continue
        try:
            raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
        except ValueError:
            continue
        if len(raw) < 4:
            continue
        cnt = rom.count(raw)
        if cnt > 1:
            dup_in_rom += 1
            # 其他出现位置是否有引用
            other_ref = False
            s = 0
            while True:
                i = rom.find(raw, s)
                if i < 0:
                    break
                if i != a and i in ref_targets:
                    other_ref = True
                    break
                s = i + 1
            if other_ref:
                dup_with_ref += 1
                if len(samples) < 8:
                    samples.append((a, e, cnt))

    print("=== 内容在 ROM 里重复的 ===")
    print(f"  重复出现: {dup_in_rom:,} / {len(zero):,}")
    print(f"  其中「另一份有引用」（本份是死数据）: {dup_with_ref:,}")
    print()

    if samples:
        print("=== 「另一份有引用」的样本 ===")
        for a, e, cnt in samples:
            print(f"  0x{a:06X} 出现 {cnt} 次  原文: {(e.get('original') or '')[:40]!r}")

    # 2. 检查这些地址是否在「文本区之间的空洞」
    print()
    print("=== 地址分布（按 64KB）===")
    zone = Counter(a >> 16 for a in zero)
    for seg, c in sorted(zone.items(), key=lambda kv: -kv[1])[:12]:
        print(f"  0x{seg:02X}0000: {c:>4}")

    # 3. 检查：与「有引用的同内容文本」比对
    print()
    print("=== 与有引用文本的内容重叠 ===")
    # 建「有引用文本」的内容集合
    ref_contents: dict[bytes, int] = {}
    for a, e in addr_to_entry.items():
        if a not in ref_targets:
            continue
        try:
            raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
        except ValueError:
            continue
        if len(raw) >= 4:
            ref_contents.setdefault(raw, a)

    overlap = 0
    for a in zero:
        e = addr_to_entry.get(a)
        if not e:
            continue
        try:
            raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
        except ValueError:
            continue
        if raw in ref_contents:
            overlap += 1
    print(f"  零引用文本中，内容与某条「有引用文本」完全相同的: {overlap:,} / {len(zero):,} "
          f"({overlap/max(len(zero),1):.1%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
