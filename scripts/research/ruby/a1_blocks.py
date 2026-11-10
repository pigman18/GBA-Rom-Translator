#!/usr/bin/env python3
"""A1.4 定案：919 条是「连续文本块」里的中间条目，块首才有引用。

已确认：919 条 100% 紧跟在其他条目之后。
所以它们不是独立项，而是「一串连续文本」里的第 2、3、4... 条。

验证：
  1. 把这些文本按地址排序，合并成「连续块」（后一条紧接前一条）
  2. 检查块首是否被引用
  3. 若块首有引用 → 整块可作为一个整体搬走（火红式）

用法：
    python scripts/research/ruby/a1_blocks.py
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

    # 全 ROM 任意对齐引用集合
    ref_targets: set[int] = set()
    for off in range(0, len(rom) - 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            ref_targets.add(v - GBA_BASE)

    zero_ref = sorted(t for t in targets if t not in ref_targets)
    standalone = [a for a in zero_ref if a > 0 and rom[a - 1] == 0xFF]
    print(f"零引用独立串: {len(standalone):,}\n")

    # 合并成连续块：后一条 addr == 前一条 addr + len
    def body_len(a: int) -> int:
        e = by_addr.get(a)
        if not e:
            return 0
        try:
            return len(bytes.fromhex((e.get("original_hex") or "").replace(" ", "")))
        except ValueError:
            return 0

    blocks = []
    cur = [standalone[0]] if standalone else []
    for a, b in zip(standalone, standalone[1:]):
        prev_len = body_len(a)
        if prev_len and b == a + prev_len:
            cur.append(b)
        else:
            blocks.append(cur)
            cur = [b]
    if cur:
        blocks.append(cur)

    print(f"=== 合并成 {len(blocks):,} 个块 ===")
    sizes = Counter(len(b) for b in blocks)
    print("  块内条目数分布（前 8）:")
    for n, c in sizes.most_common(8):
        print(f"    {n:>3} 条/块: {c:>4} 块")

    # 块首是否被引用
    head_ref = 0
    head_no = 0
    for blk in blocks:
        if blk[0] in ref_targets:
            head_ref += 1
        else:
            head_no += 1
    print()
    print("=== 块首是否被任意对齐引用 ===")
    print(f"  有引用: {head_ref:,} / {len(blocks):,} "
          f"({head_ref/max(len(blocks),1):.1%})")
    print(f"  无引用: {head_no:,}")

    # 大块样本
    print()
    print("=== 最大的 5 个块 ===")
    for blk in sorted(blocks, key=lambda b: -len(b))[:5]:
        h = blk[0]
        has = h in ref_targets
        print(f"  块首 0x{h:06X}  {len(blk)} 条  块首有引用: {has}")
        e = by_addr.get(h)
        if e:
            print(f"    首条原文: {(e.get('original') or '')[:50]!r}")

    # 块首有引用的大块 → 可直接整块搬
    movable = [b for b in blocks if b[0] in ref_targets]
    n_items = sum(len(b) for b in movable)
    print()
    print(f"=== 可整块搬的（块首有引用）===")
    print(f"  {len(movable):,} 块，共 {n_items:,} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
