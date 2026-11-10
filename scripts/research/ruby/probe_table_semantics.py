#!/usr/bin/env python3
"""打印定长名称表条目的原文/译文，核对语义是否真是「招式名」等。

为什么要做这一步：
  probe_build_vs_rom.py 证明了 build 的 original_hex 与 ROM 100% 一致，
  但那只能证明「读的是这个位置」，不能证明「这个位置放的是招式名」。
  符号表 gMoveNames=0x081C8DC8（354×13）与配置 0x1CAD04 stride=8 不一致，
  必须用可读文本确认语义。

用法：
    python scripts/research/ruby/probe_table_semantics.py
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

MODS = ["招式名", "特性名", "属性名", "道具名", "图鉴分类名", "秘密基地装饰名", "树果名", "性格名"]
SHOW = 14


def main() -> int:
    data = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = data.get("entries") or []

    for mod in MODS:
        sub = [e for e in entries if e.get("module") == mod]
        if not sub:
            continue
        print(f"=== {mod}  {len(sub)} 条 ===")
        for e in sub[:SHOW]:
            addr = e.get("address")
            o = e.get("original") or ""
            t = e.get("translated") or ""
            typ = e.get("type")
            print(f"  {addr}  [{typ:8}]  {o!r}  ->  {t!r}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
