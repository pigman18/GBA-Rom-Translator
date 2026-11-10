#!/usr/bin/env python3
"""查：道具名条目为什么 translated 是空的？

a2_item_full_chain.py 报「348 项其中 0 项有译文」，
但 build.json 里道具名有 281 条 F980 条目。
说明地址对不上 —— 可能条目 address 与 TABLE_BASE + i*40 + 0x18 不一致。

用法：
    python scripts/research/ruby/a2_item_addr_check.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
GBA_BASE = 0x08000000
TABLE_BASE = 0x39A648
ENTRY_SIZE = 40
NAME_OFF = 0x18


def main() -> int:
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    es = [e for e in d.get("entries") or [] if e.get("module") == "道具名"]
    print(f"道具名条目: {len(es)}\n")

    addrs = []
    with_text = 0
    for e in es:
        a = e.get("address") or ""
        try:
            addr = int(str(a).replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        addrs.append(addr)
        if (e.get("translated") or "").strip():
            with_text += 1

    print(f"有译文的: {with_text} / {len(es)}\n")

    print("=== 前 8 条 ===")
    for e in es[:8]:
        print(f"  {e.get('address')}  type={e.get('type')}  bl={e.get('byte_length')}")
        print(f"    orig: {(e.get('original') or '')[:36]!r}")
        print(f"    tran: {(e.get('translated') or '')[:36]!r}")
        print(f"    target_hex: {(e.get('target_hex') or '')[:50]}")

    # 地址与预期结构对比
    print()
    print("=== 地址偏差分析 ===")
    deltas = Counter()
    for a in addrs:
        # 找最近的「TABLE_BASE + i*40 + 0x18」
        base_off = a - TABLE_BASE - NAME_OFF
        if base_off >= 0:
            i = base_off // ENTRY_SIZE
            expect = TABLE_BASE + i * ENTRY_SIZE + NAME_OFF
            deltas[a - expect] += 1
        else:
            deltas["负偏移"] += 1
    print("  与「表基址+i*40+0x18」的偏差分布:")
    for k, v in deltas.most_common(8):
        print(f"    {k}: {v}")

    print()
    print(f"=== 表范围推算 ===")
    print(f"  表基址 0x{TABLE_BASE:06X}, entry_size {ENTRY_SIZE}, n=348")
    print(f"  表范围 0x{TABLE_BASE:06X}..0x{TABLE_BASE + 348*ENTRY_SIZE:06X}")
    print(f"  条目地址范围 0x{min(addrs):06X}..0x{max(addrs):06X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
