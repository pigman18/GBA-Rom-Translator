#!/usr/bin/env python3
"""texts_18: scan 模块「声明全 ROM」的真实代价 + 真正的区域重复。

关键事实链：
  1. UI界面 / 剧情 / 补漏剧情 三个模块的 start/end 都是 0x0..0xFFFFFF，
     机制上它们必须靠 filter 互斥，而不是靠地址区间——这是配置结构的隐患。
  2. 用真实条目算它们的字节占用与互相覆盖。
  3. 找出「同一段 ROM 字节被两个以上 scan 模块收录」的部分。

用法: python scripts/research/ruby/texts_18_scan_bytes.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"


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
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods = d["modules"]
    by_mod: dict[str, list] = defaultdict(list)
    for e in d["entries"]:
        by_mod[e.get("module")].append(e)

    print("=" * 116)
    print("每模块实际占用字节（按条目 byte_length 求和，去重叠后）")
    print("=" * 116)
    hdr = f"{'module':<22} {'n':>6} {'sum_len':>10} {'union':>10} {'ROM占比':>8}"
    print(hdr)
    print("-" * len(hdr))
    occ = {}
    for name, els in by_mod.items():
        total = 0
        byts = set()
        for e in els:
            a = to_int(e.get("address"))
            if a is None:
                continue
            off = a - 0x08000000 if a >= 0x08000000 else a
            ln = e.get("byte_length") or 0
            total += ln
            for k in range(off, min(off + ln, len(rom))):
                byts.add(k)
        occ[name] = byts
        print(f"{name:<22} {len(els):>6} {total:>10,} {len(byts):>10,} "
              f"{len(byts)/len(rom):>7.2%}")

    print()
    print("=" * 116)
    print("真正的区域重复：同一字节被几个模块收录")
    print("=" * 116)
    owner: dict[int, set[str]] = defaultdict(set)
    for name, byts in occ.items():
        for b in byts:
            owner[b].add(name)
    multi = {b: v for b, v in owner.items() if len(v) > 1}
    print(f"  被 ≥2 模块收录的字节: {len(multi):,}")
    pair = Counter()
    for b, v in multi.items():
        vs = sorted(v)
        for i in range(len(vs)):
            for j in range(i + 1, len(vs)):
                pair[(vs[i], vs[j])] += 1
    if pair:
        for (a, b), c in pair.most_common(20):
            print(f"    {a:<20} ∩ {b:<20} {c:>8,} bytes")
    else:
        print("    （无字节被两个模块同时收录）")

    # 定长表 vs scan 的交叠
    print()
    print("=" * 116)
    print("定长表被 scan 模块侵入的字节数")
    print("=" * 116)
    tables = [n for n, m in mods.items() if m.get("type") in ("stride", "struct")]
    scans = [n for n, m in mods.items() if m.get("type") == "scan"]
    for t in tables:
        for s in scans:
            inter = occ.get(t, set()) & occ.get(s, set())
            if inter:
                print(f"  {t:<20} ∩ {s:<12} {len(inter):>6} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
