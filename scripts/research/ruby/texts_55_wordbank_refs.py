#!/usr/bin/env python3
"""texts_55: 0x3B2 词库是否被引用 —— 回答「是否需要翻译」。

Chief 要求：搜 ROM 里有没有代码引用 0x3B219B 附近的指针，零引用就该整体跳过。

但「零引用」不能只看少量指针就下结论：剧情文本也大量零指针，
靠「基址 + 偏移」索引访问。所以要做三层判定：

  P1 直接 u32 指针指向词条的次数 / 位置分布
  P2 是否存在指向「词库基址」的指针（说明有基址+索引访问）
  P3 词库附近的指针表特征（连续 u32 数组）

同时算「词条总数」两种口径，对齐 Chief 的 847。

用法: python scripts/research/ruby/texts_55_wordbank_refs.py
"""
from __future__ import annotations

import json
import re
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
BASE = 0x08000000

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import decode_pcs  # noqa: E402

KANA = re.compile(r"^[\u3040-\u30ff\u4E00-\u9FFFー・‥．×]+$")


def main() -> int:
    rom = ROM_PATH.read_bytes()

    # ---- 口径对齐：FF 分隔 + 纯假名 + 长度>=2 ----
    LO, HI = 0x3B219B, 0x3B3900
    segs = []
    start = LO
    for i in range(LO, HI):
        if rom[i] == 0xFF:
            t = decode_pcs(rom[start:i + 1])
            if t:
                segs.append((start, t))
            start = i + 1
    words = [(o, t) for o, t in segs if KANA.match(t) and len(t) >= 2]

    print("=" * 112)
    print(f"口径对齐：0x{LO:06X}..0x{HI:06X}")
    print("=" * 112)
    print(f"  按 FF 总段数                 {len(segs)}")
    print(f"  纯假名 + 长度>=2（Chief 口径） {len(words)}")
    print()
    for o, t in words[:8]:
        print(f"    0x{o:06X} {t!r}")
    print("    ...")
    for o, t in words[-5:]:
        print(f"    0x{o:06X} {t!r}")

    # ---- P1 直接指针 ----
    print()
    print("=" * 112)
    print("P1 词条被 u32 指针直接指向的情况")
    print("=" * 112)
    word_addrs = {o for o, _ in words}
    ptr_targets: Counter[int] = Counter()
    all_targets: set[int] = set()
    for o in range(0, len(rom) - 4, 4):
        v = struct.unpack_from("<I", rom, o)[0]
        if BASE <= v < BASE + len(rom):
            t = v - BASE
            all_targets.add(t)
            if t in word_addrs:
                ptr_targets[t] += 1
    print(f"  {len(words)} 条词条中，被直接指向的: {len(ptr_targets)} 条")
    print(f"  被指向的总次数: {sum(ptr_targets.values())}")
    if ptr_targets:
        print("  明细（前 10）:")
        for a, c in ptr_targets.most_common(10):
            t = next(t for o, t in words if o == a)
            print(f"    0x{a:06X} x{c}  {t!r}")

    # ---- P2 指向区间内任意位置（含词条中间） ----
    print()
    print("=" * 112)
    print("P2 指向整个区间（含非词首位置）的指针")
    print("=" * 112)
    in_zone = [t for t in all_targets if LO <= t < HI]
    print(f"  指向 0x{LO:06X}..0x{HI:06X} 内任意位置的: {len(in_zone)} 个")
    print(f"  其中落在词条首部的: {len([t for t in in_zone if t in word_addrs])}")
    print(f"  落在词条中间/数据区的: {len([t for t in in_zone if t not in word_addrs])}")
    if in_zone:
        print(f"  样本: {[hex(x) for x in sorted(in_zone)[:12]]}")

    # ---- P3 附近是否有指针表（连续 u32 数组） ----
    print()
    print("=" * 112)
    print("P3 词库前后是否有指针表（连续 3+ 个有效 u32 指向 ROM 内）")
    print("=" * 112)
    for base in (0x3B2100, 0x3B2800, 0x3B3900, 0x3B3A00):
        run = 0
        best = 0
        for o in range(base, base + 0x200, 4):
            v = struct.unpack_from("<I", rom, o)[0]
            if BASE <= v < BASE + len(rom):
                run += 1
                best = max(best, run)
            else:
                run = 0
        print(f"  0x{base:06X} 起 0x200 内最长连续指针串: {best}")

    print()
    print("=" * 112)
    print("结论")
    print("=" * 112)
    ratio = len(ptr_targets) / max(len(words), 1)
    print(f"  词条 {len(words)} 条，被直接引用的 {len(ptr_targets)} 条 "
          f"({ratio:.1%})")
    if ratio < 0.10:
        print(f"  → 绝大多数词条无指针。若也没有「基址+索引」访问，")
        print(f"    该词库可能不被显示，不需翻译。")
    else:
        print(f"  → 有相当比例被引用，需翻译。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
