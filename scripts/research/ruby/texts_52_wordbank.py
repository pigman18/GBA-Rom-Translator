#!/usr/bin/env python3
"""texts_52: 精确定位 0x3B2 词库的干净区间与真实规模。

texts_51 发现：0x3B219B 起「按 FF 切」有 1041 段，但混杂：
  · 特性名 77 + 属性名 18 + 若干短语/道具 —— 真实词条
  · '：あ：あ：あ…' 这类填充噪声 919 条「未命中任何表」

Chief 说 869 条干净词条、起点 0x3B219B。我用词表交叉验证真实规模。

判据：
  R1 词条能在 lexicon 里命中（特性/属性/道具/招式/地点/性格/UI/短语）
  R2 或符合「干净假名/全角词」形态且不含 : 之类的分隔噪声

用法: python scripts/research/ruby/texts_52_wordbank.py
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
LEX = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "lexicon"
BASE = 0x08000000

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import decode_pcs  # noqa: E402


def load_all() -> dict[str, set[str]]:
    out = {}
    for name, fn in (("招式", "招式.json"), ("特性", "特性.json"), ("道具", "道具.json"),
                     ("属性", "属性.json"), ("性格", "性格.json"), ("图鉴", "图鉴.json"),
                     ("地点", "地点.json"), ("短语", "短语.json"), ("UI", "UI.json")):
        p = LEX / fn
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                out[name] = {k for k in d if isinstance(k, str)}
        except Exception:
            pass
    return out


def main() -> int:
    rom = ROM_PATH.read_bytes()
    cats = load_all()
    allwords = set().union(*cats.values())
    print(f"词表合计 {len(allwords):,}")

    LO, HI = 0x3B2000, 0x3B7000
    segs = []
    start = LO
    for i in range(LO, HI):
        if rom[i] == 0xFF:
            t = decode_pcs(rom[start:i + 1])
            if t:
                segs.append((start, t))
            start = i + 1

    # 分类
    real, filler, other = [], [], []
    for off, t in segs:
        if t in allwords:
            real.append((off, t))
        elif re.fullmatch(r"[：あぜをいァ]+", t) or t.count("：") >= 3:
            filler.append((off, t))
        else:
            other.append((off, t))

    print()
    print("=" * 112)
    print("按性质分类")
    print("=" * 112)
    print(f"  R1 词表命中（真词条）      : {len(real)}")
    print(f"  R2 填充噪声（：あぜ 重复） : {len(filler)}")
    print(f"  R3 其它                    : {len(other)}")

    print()
    print("=" * 112)
    print("R1 真词条：地址跨度与分类")
    print("=" * 112)
    if real:
        print(f"  0x{real[0][0]:06X} .. 0x{real[-1][0]:06X}")
        c = Counter()
        for _, t in real:
            for n, ks in cats.items():
                if t in ks:
                    c[n] += 1
                    break
        for k, v in c.most_common():
            print(f"    {k:<8} {v}")
        # 找连续区段
        print()
        print("  连续密度（按 0x200 分桶，看真词条在哪段集中）")
        buck = Counter(o >> 9 for o, _ in real)
        for b in sorted(buck):
            print(f"    0x{b<<9:06X}: {'#' * min(buck[b], 60)} {buck[b]}")

    print()
    print("=" * 112)
    print("R3 其它（前 25 条，看是不是真词条但不在词表）")
    print("=" * 112)
    for off, t in other[:25]:
        print(f"  0x{off:06X} {t!r}")

    print()
    print("=" * 112)
    print("指针统计（对 R1 真词条）")
    print("=" * 112)
    targets: set[int] = set()
    for o in range(0, len(rom) - 4, 4):
        v = struct.unpack_from("<I", rom, o)[0]
        if BASE <= v < BASE + len(rom):
            targets.add(v - BASE)
    wp = [o for o, _ in real if o in targets]
    print(f"  {len(wp)}/{len(real)} 有 u32 指针")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
