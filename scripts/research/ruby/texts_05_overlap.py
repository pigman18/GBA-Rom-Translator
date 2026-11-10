#!/usr/bin/env python3
"""texts_05: 模块间区域重叠 + 条目级重复（同一 ROM 字节被多个模块收录）。

两件事：
  A. 模块声明的 [start, end] 两两求交（结构表/定长表用声明区间；
     scan 模块用其 entries 的实际最小/最大地址）。
  B. 条目级：按 entries 的 (address, len) 求覆盖区间，看同一 ROM 字节是否被
     多个模块收录（这是「重复出现」的最硬证据）。

用法: python scripts/research/ruby/texts_05_overlap.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
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
    mods = d["modules"]
    entries = d["entries"]

    by_mod: dict[str, list] = defaultdict(list)
    for e in entries:
        by_mod[e.get("module")].append(e)

    # ---- A. 声明区间两两求交 ----
    spans = {}
    for name, m in mods.items():
        s = to_int(m.get("start"))
        e = to_int(m.get("end"))
        els = by_mod.get(name, [])
        addrs = []
        for x in els:
            a = to_int(x.get("address"))
            if a is not None:
                addrs.append(a - GBA_BASE if a >= GBA_BASE else a)
        spans[name] = {
            "decl_start": s, "decl_end": e,
            "real_start": min(addrs) if addrs else None,
            "real_end": max(addrs) if addrs else None,
            "n": len(els),
        }

    print("=" * 120)
    print("A. 模块「实际覆盖」区间（结构/定长表用声明区间，scan 用 entries 实际范围）")
    print("=" * 120)
    for name, sp in spans.items():
        lo = sp["decl_start"] if sp["decl_start"] not in (None, 0) else sp["real_start"]
        hi = sp["decl_end"] if sp["decl_end"] not in (None, 0xFFFFFF) else sp["real_end"]
        sp["eff_lo"], sp["eff_hi"] = lo, hi
        print(f"  {name:<22} 0x{lo:06X}..0x{hi:06X}  "
              f"(声明 0x{sp['decl_start']:06X}..0x{sp['decl_end']:06X}) n={sp['n']}")

    print()
    print("=" * 120)
    print("A2. 声明/实际区间两两重叠")
    print("=" * 120)
    names = list(spans)
    any_ov = False
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = spans[names[i]], spans[names[j]]
            lo = max(a["eff_lo"], b["eff_lo"])
            hi = min(a["eff_hi"], b["eff_hi"])
            if lo <= hi:
                any_ov = True
                print(f"  {names[i]:<20} ∩ {names[j]:<20} = 0x{lo:06X}..0x{hi:06X}  "
                      f"({hi - lo + 1} bytes)")
    if not any_ov:
        print("  （无）")

    # ---- B. 条目级字节覆盖重复 ----
    print()
    print("=" * 120)
    print("B. 条目级：同一 ROM 字节被多少模块收录")
    print("=" * 120)
    # 只比较非全 ROM scan 的模块，避免全 ROM 必然重叠的噪音
    byte_owners: dict[int, set[str]] = defaultdict(set)
    for e in entries:
        a = to_int(e.get("address"))
        if a is None:
            continue
        off = a - GBA_BASE if a >= GBA_BASE else a
        ln = e.get("byte_length") or 0
        mod = e.get("module")
        for k in range(off, off + max(ln, 1)):
            byte_owners[k].add(mod)

    multi = {k: v for k, v in byte_owners.items() if len(v) > 1}
    print(f"  被 >1 模块覆盖的字节数: {len(multi):,} / {len(byte_owners):,}")
    pair_cnt: dict[tuple[str, str], int] = defaultdict(int)
    for k, v in multi.items():
        vs = sorted(v)
        for i in range(len(vs)):
            for j in range(i + 1, len(vs)):
                pair_cnt[(vs[i], vs[j])] += 1
    print()
    print("  按模块对统计（字节数）:")
    for (a, b), c in sorted(pair_cnt.items(), key=lambda kv: -kv[1]):
        print(f"    {a:<20} ∩ {b:<20} {c:>8,} bytes")

    # ---- C. 内容完全重复的条目 ----
    print()
    print("=" * 120)
    print("C. 内容完全重复的条目（同 original_hex，不同地址）")
    print("=" * 120)
    by_hex: dict[str, list] = defaultdict(list)
    for e in entries:
        h = (e.get("original_hex") or "").replace(" ", "").lower()
        if h:
            by_hex[h].append(e)
    dup_groups = {h: v for h, v in by_hex.items() if len(v) > 1}
    total_dup_entries = sum(len(v) - 1 for v in dup_groups.values())
    print(f"  重复内容组: {len(dup_groups):,}  冗余条目数（可删）: {total_dup_entries:,}")
    by_mod_dup: dict[str, int] = defaultdict(int)
    for h, v in dup_groups.items():
        for e in v[1:]:
            by_mod_dup[e.get("module")] += 1
    print()
    for m, c in sorted(by_mod_dup.items(), key=lambda kv: -kv[1]):
        print(f"    {m:<22} 冗余 {c:>5}")
    print()
    print("  样本（前 15 组）:")
    for h, v in list(sorted(dup_groups.items(), key=lambda kv: -len(kv[1])))[:15]:
        locs = ", ".join(f"0x{to_int(e.get('address')) & 0xFFFFFF:06X}[{e.get('module')}]"
                         for e in v[:4])
        print(f"    len={len(h)//2:>3} x{len(v)}  {locs}  {(v[0].get('original') or '')[:36]!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
