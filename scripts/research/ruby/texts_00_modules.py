#!/usr/bin/env python3
"""texts_00: 盘点 texts.json 的 22 个模块——几何参数、条目数、地址范围。

只读，不改任何文件。
用法: python scripts/research/ruby/texts_00_modules.py
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
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
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
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods: dict = d["modules"]
    entries = d["entries"]

    by_mod: dict[str, list] = {}
    for e in entries:
        by_mod.setdefault(e.get("module"), []).append(e)

    print(f"modules={len(mods)}  entries={len(entries)}  count={d.get('count')}")
    print()

    hdr = f"{'#':>3} {'module':<24} {'type':<10} {'start':>10} {'end':>10} {'span':>8} {'n_cfg':>6} {'n_ent':>6}  read"
    print(hdr)
    print("-" * len(hdr))
    rows = []
    for i, (name, m) in enumerate(mods.items()):
        r = m.get("read") or {}
        w = m.get("write") or {}
        start = to_int(m.get("start"))
        end = to_int(m.get("end"))
        span = (end - start) if (start is not None and end is not None) else None
        els = by_mod.get(name, [])
        n_cfg = r.get("count") or r.get("n") or r.get("count_entries")
        rows.append((i, name, m, start, end, span, els))
        readdesc = json.dumps(r, ensure_ascii=False, separators=(",", ":"))
        print(f"{i:>3} {name:<24} {str(m.get('type')):<10} "
              f"{(f'0x{start:X}' if start is not None else '-'):>10} "
              f"{(f'0x{end:X}' if end is not None else '-'):>10} "
              f"{(str(span) if span is not None else '-'):>8} "
              f"{str(n_cfg):>6} {len(els):>6}  {readdesc}")

    print()
    print("=" * 130)
    print("逐模块完整定义")
    print("=" * 130)
    for i, name, m, start, end, span, els in rows:
        print(f"\n[{i:>2}] {name}   label={m.get('label')!r} group={m.get('group')!r}")
        print("     " + json.dumps(m, ensure_ascii=False, indent=2).replace("\n", "\n     "))
        if els:
            addrs = [to_int(e.get("address")) for e in els]
            addrs = [a for a in addrs if a is not None]
            if addrs:
                print(f"     entries: n={len(els)} addr_min=0x{min(addrs):08X} "
                      f"addr_max=0x{max(addrs):08X}")
            cnt = Counter(e.get("module") for e in els)
            tl = Counter(e.get("translated") != "" for e in els)
            print(f"     translated filled: {tl.get(True,0)} / empty: {tl.get(False,0)}")
            fb = [e for e in els if "fallback" in e]
            if fb:
                print(f"     fallback entries: {len(fb)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
