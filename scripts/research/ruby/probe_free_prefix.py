#!/usr/bin/env python3
"""找真正可用的前缀字节——基于真实抽取文本的字节占用表。

0xF7 已排除（62 条真实文本在用，多为 FC 0C F7 颜色参数）。

本脚本对全部 12,697 条真实文本统计每个字节的出现次数，
并按「是否出现在串体内（非控制码位置）」分类，找出真正空闲的字节。

判据：
  真正安全的候选 = 在真实文本里**从不出现**，或只作为其他控制码的参数出现、
  且不会被独立消费的字节。

用法：
    python scripts/research/ruby/probe_free_prefix.py
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


def main() -> int:
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = d.get("entries") or []

    freq: Counter = Counter()
    n_entries = 0
    for e in entries:
        oh = (e.get("original_hex") or "").replace(" ", "").lower()
        if not oh:
            continue
        try:
            raw = bytes.fromhex(oh)
        except ValueError:
            continue
        n_entries += 1
        for b in raw:
            freq[b] += 1

    print(f"真实文本条目 {n_entries:,}\n")

    print("=== 全部 256 字节的出现频率（升序，找空闲字节）===")
    rare = sorted(range(256), key=lambda b: freq.get(b, 0))
    for b in rare[:40]:
        c = freq.get(b, 0)
        char = chr(b) if 0x20 <= b < 0x7F else "."
        print(f"  0x{b:02X} ({char}): {c:>7,}")
    print()

    print("=== 高位字节 0xF0..0xFF（表情/控制区）===")
    for b in range(0xF0, 0x100):
        c = freq.get(b, 0)
        print(f"  0x{b:02X}: {c:>7,}")

    print()
    print("=== 候选评估 ===")
    # F9 已用（CHS_ESCAPE），FA-FF 是控制码
    # 看 0xF7/0xF8 之外还有哪些没被用
    print("  0xF9 = CHS_ESCAPE（已占用）")
    print("  0xFA..0xFF = PCS/控制码")
    print("  0xF7 = [angry] 表情 + FC 0C 颜色参数（实测 62 条在用，不可占用）")
    for b in (0xF8, 0xF6, 0xF5, 0xF4, 0xF3, 0xF2, 0xF1, 0xF0):
        c = freq.get(b, 0)
        print(f"  0x{b:02X}: 真实文本出现 {c:,} 次"
              + ("  ← 大量在用，不可占用" if c > 20 else "  ← 少量，需逐个确认语义"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
