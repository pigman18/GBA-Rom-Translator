#!/usr/bin/env python3
"""texts_04: 打印指定模块的全部条目明细（地址 / hex / 原文），用于逐条核对。

用法: python scripts/research/ruby/texts_04_entries.py --module 性格名 [--limit 50]
      python scripts/research/ruby/texts_04_entries.py --all-summary
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
GBA_BASE = 0x08000000


def to_int(v):
    if v is None:
        return None
    if isinstance(v, int):
        return v
    s = str(v).strip()
    try:
        return int(s, 16) if s.lower().startswith("0x") else int(s, 10)
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--module")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--skip", type=int, default=0)
    a = ap.parse_args()

    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    entries = d["entries"]

    if not a.module:
        ap.error("需要 --module")
    els = [e for e in entries if e.get("module") == a.module]
    print(f"module={a.module} n={len(els)}\n")
    print(f"{'#':>4} {'address':>12} {'off':>10} {'len':>4} {'hex':<42} original")
    print("-" * 130)
    for i, e in enumerate(els):
        if i < a.skip:
            continue
        if i >= a.skip + a.limit:
            break
        addr = to_int(e.get("address")) or 0
        off = addr - GBA_BASE if addr >= GBA_BASE else addr
        h = (e.get("original_hex") or "")
        orig = (e.get("original") or "").replace("\n", "\\n")
        print(f"{i:>4} 0x{addr:08X} 0x{off:06X} {e.get('byte_length'):>4} {h:<42} {orig}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
