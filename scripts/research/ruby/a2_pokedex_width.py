#!/usr/bin/env python3
"""图鉴分类名：名字的真实可用宽度是多少？

已知：
  stride=28, name_offset=0, 386/386 ROM 字节与 original_hex 一致
  原文最长 6B

看条目：
  0x38474C: 20 06 08 16 2e 00 00 00 00 00 00 00 7d db 37 08 ...
            └─名字'みかくにん'─┘ 零填充到 +0x0C，然后是指针

  0x384768: 10 18 00 00 00 00 07 00 45 00 00 00 9c db 37 08 ...
            └'たね'┘ 零填充到 +0x06，然后 07 00 / 45 00 ...

所以名字后面是 0x00 填充，但填充到哪由「下一个非零字段」决定，不固定。

关键问题：代码怎么知道名字多长？靠 0xFF 还是 0x00？

看 0x384848: 0a 03 27 00 00 00 10 00 57 03 ...
  'こうら' = 0a 03 27，然后 00 00 00 —— 是 0x00 结尾，不是 FF！

⇒ **图鉴分类名用 0x00 结尾（eos=0）**，这正是 texts.json 里 `"eos": 0` 的含义！

用法：
    python scripts/research/ruby/a2_pokedex_width.py
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
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
GBA_BASE = 0x08000000
BASE = 0x38474C
STRIDE = 28
N = 386


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    items = {}
    for e in d.get("entries") or []:
        if e.get("module") != "图鉴分类名":
            continue
        try:
            a = int(str(e.get("address") or "0x0").replace("0x", ""), 16)
        except ValueError:
            continue
        if a >= GBA_BASE:
            a -= GBA_BASE
        items[a] = e

    print("=== 检验：名字用 0x00 结尾（eos=0）===")
    ok = 0
    for i in range(20):
        off = BASE + i * STRIDE
        e = items.get(off)
        if not e:
            continue
        try:
            raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
        except ValueError:
            continue
        seg = rom[off:off + STRIDE]
        # 名字之后第一个字节
        nextb = seg[len(raw)] if len(raw) < len(seg) else None
        mark = "✅" if nextb == 0x00 else f"⚠️ 0x{nextb:02X}" if nextb is not None else "?"
        if nextb == 0x00:
            ok += 1
        print(f"  item{i:>3} 0x{off:06X} {e.get('original')!r:<14} "
              f"len={len(raw):>2}  后一字节 {mark}")
    print(f"\n  前 20 项中 0x00 结尾: {ok}")
    print()

    # 每项的名字后「第一个非零字节」位置 = 元数据起点
    print("=== 元数据起点分布（名字后第一个非零）===")
    starts = Counter()
    for i in range(N):
        off = BASE + i * STRIDE
        e = items.get(off)
        if not e:
            continue
        try:
            raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
        except ValueError:
            continue
        seg = rom[off:off + STRIDE]
        p = len(raw)
        while p < len(seg) and seg[p] == 0x00:
            p += 1
        starts[p] += 1
    for p, c in sorted(starts.items()):
        print(f"  元数据从 +{p:>2} 开始: {c} 项")

    # 名字最长 6B → 若元数据最早从 +7 开始，名字可用宽度就是 7?
    print()
    print("=== 关键判断 ===")
    max_name = max(len(bytes.fromhex((e.get('original_hex') or '').replace(' ', '')))
                   for e in items.values() if e.get('original_hex'))
    min_meta = min(starts) if starts else STRIDE
    print(f"  原文最长 {max_name}B")
    print(f"  元数据最早起点 +{min_meta}")
    print(f"  ⇒ 名字可用宽度 = {min_meta} 字节（保守）")
    print()
    print("  中文 F9 00 hi lo = 4B/字：")
    for k in range(1, 6):
        need = 4 * k + 1     # 加 0x00 结尾
        ok_k = "✓" if need <= min_meta else "✗"
        print(f"    {k} 字 = {need}B {ok_k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
