#!/usr/bin/env python3
"""A1 终极问题：4,180 条「5 字节内无指针」的剧情文本，游戏怎么读到它们？

可能性：
  A. 被脚本 VM 按「脚本地址 + 偏移」内联访问（message op 后跟字面串）
  B. 被某个「主文本指针表」整体引用（表在别处，元素是这些文本地址）
  C. 是长串的一部分，extract 切错了
  D. 通过 DMA/压缩包加载

本脚本检验 B：这些文本地址是否**成组连续**，且能找到引用它们的「指针表」。

判据：若 N 条文本地址连续递增（间隔=文本长度+1），说明它们是一整块，
      只需找到指向块首的指针即可整块搬。

用法：
    python scripts/research/ruby/a1_contiguous.py
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
    no_ptr = own.get("NO_PTR") or []
    addrs = sorted(int(r["addr"].replace("0x", ""), 16) for r in no_ptr)
    print(f"NO_PTR 条目 {len(addrs):,}\n")

    # 1. 连续性分析：相邻条目 addr2 == addr1 + len(body1) + 1 ?
    contiguous = 0
    gaps = Counter()
    for a, b in zip(addrs, addrs[1:]):
        e = by_addr.get(a)
        if not e:
            continue
        try:
            raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
        except ValueError:
            continue
        expected = a + len(raw)      # raw 已含结尾 FF
        if b == expected:
            contiguous += 1
        gaps[b - a] += 1

    print("=== 相邻 NO_PTR 条目是否首尾相接 ===")
    print(f"  完全相接（b = a + len）: {contiguous:,} / {len(addrs)-1:,} "
          f"({contiguous/max(len(addrs)-1,1):.1%})")
    print("  间距分布（前 10）:")
    for g, c in gaps.most_common(10):
        print(f"    {g:>8} 字节: {c:>5}")
    print()

    # 2. 找「块首」：前面不与自己相邻的那些
    blocks = []
    cur_start = addrs[0] if addrs else None
    for a, b in zip(addrs, addrs[1:]):
        e = by_addr.get(a)
        try:
            raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
            exp = a + len(raw)
        except ValueError:
            exp = None
        if exp is None or b != exp:
            blocks.append((cur_start, a))
            cur_start = b
    if addrs:
        blocks.append((cur_start, addrs[-1]))

    print(f"=== 连块分析：{len(blocks):,} 个块 ===")
    sizes = Counter()
    for s, e_ in blocks:
        n = sum(1 for a in addrs if s <= a <= e_)
        sizes[n] += 1
    print("  块内条目数分布（前 8）:")
    for n, c in sizes.most_common(8):
        print(f"    每块 {n:>3} 条: {c:>4} 个块")
    print()

    # 3. 块首是否有指针（若有，整块可搬）
    idx = set()
    for off in range(0, len(rom) - 4, 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            idx.add(v - GBA_BASE)

    head_ptr = 0
    for s, e_ in blocks:
        if s in idx:
            head_ptr += 1
    print("=== 块首是否有指针 ===")
    print(f"  有指针的块首: {head_ptr:,} / {len(blocks):,} "
          f"({head_ptr/max(len(blocks),1):.1%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
