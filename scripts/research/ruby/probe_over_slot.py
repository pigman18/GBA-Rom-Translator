#!/usr/bin/env python3
"""F980 条目的「译文正文 F900 长度」vs「槽宽」——真实超槽比例。

上一脚本显示：7,144 条 F980 的 target_hex（5 字节短语引用）全部塞得下，
那不是重点。重点是「如果用 F900 内联写译文正文，需要多少字节，超没超槽」。

用法：
    python scripts/research/ruby/probe_over_slot.py
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
sys.path.insert(0, str(ROOT / "src"))
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"


def main() -> int:
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path

    cm = Charmap(charmap_path=get_charmap_path("POKEMON_RUBY_AXVJ00"),
                 target_lang="zh-Hans")

    d = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = d.get("entries") or []
    phrases = d.get("phrases") or []
    code2text = {i: s for i, s in enumerate(phrases) if s}

    f980 = [e for e in entries
            if e.get("type") == "replace" and e.get("phrase_code") is not None]
    print(f"F980 条目 {len(f980):,}，短语表 {len(code2text):,} 条\n")

    fits = 0
    over = 0
    over_by_mod: Counter = Counter()
    ratios = []

    for e in f980:
        code = e.get("phrase_code")
        text = code2text.get(code)
        if not text:
            continue
        try:
            body = cm.encode(text)
        except Exception:
            continue
        # 去掉尾部 FF 再算（槽里要留 FF）
        need = len(body)
        cap = int(e.get("byte_length") or 0)
        if not cap:
            continue
        ratios.append(need / cap)
        if need <= cap:
            fits += 1
        else:
            over += 1
            over_by_mod[e.get("module")] += 1

    total = fits + over
    print(f"=== F900 内联写正文 vs 槽宽（{total:,} 条可测）===")
    print(f"  塞得下: {fits:,} ({fits/total:.1%})")
    print(f"  超槽:   {over:,} ({over/total:.1%})")
    if ratios:
        ratios.sort()
        print(f"  长度比 中位数 {ratios[len(ratios)//2]:.2f}x"
              f"  90分位 {ratios[int(len(ratios)*0.9)]:.2f}x"
              f"  最大 {ratios[-1]:.1f}x")
    print()
    print("=== 超槽条目按模块 ===")
    for mod, n in over_by_mod.most_common(12):
        print(f"  {mod:<18} {n:>5}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
