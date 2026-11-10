#!/usr/bin/env python3
"""查 01 F7（全角空格）的 24 条实际用法，判断能否改成 0x00。

背景：
  charmap.py:26  _DEFAULT_IDEOSPACE = bytes([0x01, 0xF7])
  产物里 01 F7 出现 535 次，build.json 有 24 条 target_hex 含 01f7。
  F7 要作中文前缀，必须处理这个冲突。

做法：列出这 24 条的模块、原文、译文，看是「文字里的空格」还是「排版占位」。

用法：
    python scripts/research/ruby/probe_ideospace.py
"""
from __future__ import annotations

import json
import sys
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

    hits = []
    for e in entries:
        th = (e.get("target_hex") or "").replace(" ", "").lower()
        if "01f7" in th:
            hits.append(e)

    print(f"build.json 含 01f7 的条目: {len(hits)}\n")
    for e in hits:
        print(f"  module={e.get('module')}  addr={e.get('address')}  type={e.get('type')}")
        print(f"    original  : {e.get('original')!r}")
        print(f"    translated: {e.get('translated')!r}")
        print(f"    target_hex: {e.get('target_hex')}")
        print()

    # 译文里是否真有空格字符
    with_space = sum(1 for e in hits if " " in (e.get("translated") or ""))
    print(f"译文含 ASCII 空格的: {with_space}/{len(hits)}")
    print(f"译文含全角空格的: {sum(1 for e in hits if chr(0x3000) in (e.get('translated') or ''))}/{len(hits)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
