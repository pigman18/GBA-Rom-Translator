#!/usr/bin/env python3
"""A1.4：919 条「完整独立串、零引用」的文本，游戏怎么读到？

已排除：
  - 任意对齐的绝对指针（0 命中）
  - 块首指针（0 命中）

待查假设：
  A. 基址+索引 访问（表里存的是「偏移」而不是绝对地址）
  B. LD 压缩包内含指针
  C. 被「文本偏移表」引用（u16 偏移而不是 u32 绝对地址）
  D. 前一条目连写时被算作同一段（extract 切碎）

本脚本检验 A/C：用「16 位偏移」「相对基址的差值」反查。

用法：
    python scripts/research/ruby/a1_919_refs.py
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
    by_addr = {}
    for e in d.get("entries") or []:
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

    # 先找出「零引用」集合
    covered = set()
    for off in range(0, len(rom) - 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            t = v - GBA_BASE
            if t in targets:
                covered.add(t)

    zero_ref = sorted(targets - covered)
    # 只要「前一字节是 FF」的完整独立串
    standalone = []
    for a in zero_ref:
        if a > 0 and rom[a - 1] == 0xFF:
            standalone.append(a)

    print(f"零引用条目 {len(zero_ref):,}，其中完整独立串 {len(standalone):,}\n")

    # ---- 假设 C：16 位偏移表 ----
    # 文本区基址候选
    bases = [0x140000, 0x150000, 0x1C0000, 0x1D0000, 0x1E0000, 0x100000]
    print("=== 假设：16 位偏移引用（相对某个基址）===")
    hit16 = 0
    for a in standalone[:]:
        for base in bases:
            off16 = a - base
            if 0 <= off16 < 0x10000:
                pat = struct.pack("<H", off16)
                c = rom.count(pat)
                if c > 0:
                    hit16 += 1
                    break
    print(f"  16 位偏移能命中的: {hit16:,} / {len(standalone):,}")
    print("  （命中不代表有效，16 位值太小会大量误报）")

    # ---- 假设 A：前一条目的「后续」引用 ----
    # 若文本 A 在文本 B 之后，B 的指针可能被覆盖 A 区段
    print()
    print("=== 检查：这些文本是否紧跟在某个有条目的文本之后 ===")
    adjacent = 0
    for a in standalone:
        # 找 a 之前 512 字节内是否有条目起点
        for delta in range(1, 513):
            if (a - delta) in by_addr:
                adjacent += 1
                break
    print(f"  前 512B 内有条目起点: {adjacent:,} / {len(standalone):,} "
          f"({adjacent/max(len(standalone),1):.1%})")

    # ---- 假设 B：是否在某个压缩区 ----
    print()
    print("=== 这些文本的地址分布 ===")
    zone = Counter()
    for a in standalone:
        zone[a >> 16] += 1
    for seg, c in sorted(zone.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  0x{seg:02X}0000..0x{seg:02X}FFFF: {c:>4}")

    # ---- 样本详查 ----
    print()
    print("=== 样本前后 32 字节（看是否有隐藏索引）===")
    for a in standalone[:6]:
        e = by_addr.get(a)
        raw = b""
        if e:
            try:
                raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
            except ValueError:
                pass
        print(f"  0x{a:06X}  len={len(raw)}")
        print(f"    -24..: {rom[max(0,a-24):a].hex(' ')}")
        print(f"    body : {raw[:32].hex(' ')}")
        print(f"    +end : {rom[a+len(raw):a+len(raw)+16].hex(' ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
