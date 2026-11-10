#!/usr/bin/env python3
"""texts_53: 0x3B2 词库的真实起点/终点 + 与 Chief「869 条」口径对齐。

texts_52 事实：
  · 0x3B2000..0x3B2800 是数据区（裸 F7、Ä、超长串、零词表命中）
  · 真词库从 0x3B2800 附近开始（0x3B2800 桶 69 条、0x3B2A00 桶 37 条）
  · 122 条命中词表：特性 77 + 属性 18 + 其它 27

Chief 说 869 条、起点 0x3B219B。差异在于**「干净词条」的定义**：
他可能把「形态干净的全角词」都算进去（含不在我词表里的），
我按「命中 lexicon」算只有 122 条。

本脚本用**逐字节扫描法**找词库边界：
从 0x3B2800 开始，逐条按 FF 切，统计「干净形态」条目的连续区间。

用法: python scripts/research/ruby/texts_53_bank_bounds.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
LEX = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "lexicon"

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import decode_pcs  # noqa: E402


def load_all() -> set[str]:
    v = set()
    for p in LEX.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                v.update(k for k in d if isinstance(k, str))
        except Exception:
            pass
    return v


KANA = re.compile(r"^[\u3040-\u30ff\uFF10-\uFF5A\u4E00-\u9FFFー・‥．×]+$")


def main() -> int:
    rom = ROM_PATH.read_bytes()
    vocab = load_all()

    print("=" * 112)
    print("从 0x3B2800 起逐条列（看真实词库长什么样）")
    print("=" * 112)
    LO, HI = 0x3B2800, 0x3B2C00
    segs = []
    start = LO
    for i in range(LO, HI):
        if rom[i] == 0xFF:
            t = decode_pcs(rom[start:i + 1])
            if t:
                segs.append((start, t))
            start = i + 1
    kana_ok = 0
    for off, t in segs:
        flag = "词表" if t in vocab else ("形态" if KANA.match(t) else "噪声")
        if KANA.match(t):
            kana_ok += 1
        print(f"  0x{off:06X} [{flag}] {t!r}")

    print()
    print("=" * 112)
    print("全区间统计：按「形态干净」口径数条数（对齐 Chief 的 869）")
    print("=" * 112)
    for lo in (0x3B2800, 0x3B219B, 0x3B2000):
        segs2 = []
        start = lo
        for i in range(lo, 0x3B7000):
            if rom[i] == 0xFF:
                t = decode_pcs(rom[start:i + 1])
                if t:
                    segs2.append((start, t))
                start = i + 1
        kana = [(o, t) for o, t in segs2 if KANA.match(t)]
        vocab_hit = [(o, t) for o, t in kana if t in vocab]
        print(f"\n  lo=0x{lo:06X}:")
        print(f"    按 FF 总段数       {len(segs2)}")
        print(f"    形态干净（假名全角） {len(kana)}")
        print(f"    其中命中词表       {len(vocab_hit)}")
        if kana:
            print(f"    地址跨度 0x{kana[0][0]:06X} .. 0x{kana[-1][0]:06X}")
            print(f"    前 5 条: {[t for _, t in kana[:5]]}")
            print(f"    后 5 条: {[t for _, t in kana[-5:]]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
