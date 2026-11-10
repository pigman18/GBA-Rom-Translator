#!/usr/bin/env python3
"""A1.4 定案：919 条所在区域（0x3Bxxxx / 0x18xxxx）由什么访问。

发现：
  - 919 条合并成 381 块，块首 0/381 有引用
  - 最大块 0x3B37D4（35 条）、0x18C492（23 条）都在「表区」
  - 0x3B0000..0x3BFFFF 独占 669 条

推论：这些是「按基址+固定长度/索引」访问的表区文本。
若 0x3B0000 区段是某个结构体数组，文本就在结构体内部。

验证：检查 0x3B0000 区段的结构规律（步长、字段偏移）。

用法：
    python scripts/research/ruby/a1_3b_zone.py
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

    ref_targets: set[int] = set()
    for off in range(0, len(rom) - 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            ref_targets.add(v - GBA_BASE)

    zero = sorted(t for t in targets if t not in ref_targets and t > 0 and rom[t-1] == 0xFF)

    # 聚焦 0x3B0000 段
    zone = [a for a in zero if 0x3B0000 <= a < 0x3C0000]
    print(f"0x3B0000..0x3C0000 段内零引用独立串: {len(zone):,}\n")

    if zone:
        # 相邻条目间距
        gaps = Counter()
        for a, b in zip(zone, zone[1:]):
            gaps[b - a] += 1
        print("=== 相邻文本起点间距（前 12）===")
        for g, c in gaps.most_common(12):
            print(f"    {g:>6} 字节: {c:>4}")

        # 找步长：若大量间距是同一个值的倍数，就是结构体步长
        print()
        print("=== 间距是否为某个步长的倍数 ===")
        for step in (16, 20, 24, 28, 32, 36, 40, 44, 48, 56, 64):
            mult = sum(c for g, c in gaps.items() if g % step == 0 and g > 0)
            total = sum(gaps.values())
            if total and mult / total > 0.6:
                print(f"  步长 {step}: {mult}/{total} ({mult/total:.0%}) 的间距是其倍数")

        print()
        print(f"=== 前 10 条（看内容）===")
        for a in zone[:10]:
            e = by_addr.get(a)
            try:
                raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
            except (ValueError, AttributeError):
                raw = b""
            print(f"  0x{a:06X} len={len(raw):>3}  {(e.get('original') or '')[:40]!r}")

        # 检查区段前后是否有「索引表」
        lo = min(zone)
        print()
        print("=== 段起始附近 0x%06X 往前 64 字节 ===" % lo)
        print(f"  {rom[max(0,lo-64):lo].hex(' ')}")

    # 全 ROM：找哪些 0x3B0000 区段附近的 u32 指向它
    print()
    print("=== 指向 0x3B0000..0x3C0000 的指针（任意对齐）===")
    cnt = 0
    samples = []
    for off in range(0, len(rom) - 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE + 0x3B0000 <= v < GBA_BASE + 0x3C0000:
            cnt += 1
            if len(samples) < 8:
                samples.append((off, v - GBA_BASE))
    print(f"  共 {cnt:,} 个")
    for off, tgt in samples:
        print(f"    0x{off:06X} → 0x{tgt:06X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
