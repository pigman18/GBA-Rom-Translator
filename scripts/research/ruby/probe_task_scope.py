#!/usr/bin/env python3
"""为 TASKS.md 核对任务规模：F980 各模块的「为什么没走 relocate」。

判据：看 build.json 里各 F980 条目的 pointer_sources 情况 + 模块 write 开关，
判断「移除 F980」的真实工作量分布。

用法：
    python scripts/research/ruby/probe_task_scope.py
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
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"


def main() -> int:
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = d.get("entries") or []
    mods = (json.loads(TEXTS.read_text(encoding="utf-8")).get("modules") or {})

    f980 = [e for e in entries
            if e.get("type") == "replace"
            and e.get("phrase_code") is not None]

    print(f"F980 条目 {len(f980):,}\n")

    print("=== 按模块：是否有 pointer_sources（有则本可 relocate）===")
    rows = []
    for mod, items in sorted(
        ((m, [e for e in f980 if e.get("module") == m])
         for m in {e.get("module") for e in f980}),
        key=lambda kv: -len(kv[1]),
    ):
        has_ptr = sum(1 for e in items if e.get("pointer_sources"))
        meta = mods.get(mod) or {}
        w = meta.get("write") or {}
        typ = meta.get("type") or "?"
        rows.append((mod, len(items), has_ptr, typ,
                     w.get("relocate", "d"), w.get("replace", "d"), w.get("slot", "d")))

    print(f"  {'模块':<18} {'条数':>5} {'有指针':>6}  {'type':<11} reloc repl slot")
    for mod, n, hp, typ, r, rp, s in rows:
        print(f"  {mod:<18} {n:>5} {hp:>6}  {typ:<11} {str(r):<5} {str(rp):<4} {s}")

    total_ptr = sum(r[2] for r in rows)
    print(f"\n  有 pointer_sources 的 F980 条目合计: {total_ptr:,} / {len(f980):,}")

    print("\n=== 按槽宽分布（决定能否塞下）===")
    bl = Counter()
    for e in f980:
        bl[int(e.get("byte_length") or 0)] += 1
    for k in sorted(bl)[:14]:
        print(f"  byte_length={k:<4} {bl[k]:>5}")

    print("\n=== 译文长度 vs 槽宽（多少条其实塞得下 F900）===")
    fits = over = 0
    for e in f980:
        th = (e.get("target_hex") or "").replace(" ", "")
        try:
            n = len(bytes.fromhex(th))
        except ValueError:
            continue
        cap = int(e.get("byte_length") or 0)
        if cap and n <= cap:
            fits += 1
        else:
            over += 1
    print(f"  当前 target_hex 已塞得下: {fits:,}")
    print(f"  超出槽宽（靠 F980 才落地）: {over:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
