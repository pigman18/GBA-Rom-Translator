#!/usr/bin/env python3
"""texts_11: scan 模块（剧情/补漏剧情/UI界面）的条目是否误收进「已定界的结构表」。

这是「重复覆盖同一片区域」的字节级判据：
  若 scan 把某条文本的起点落在 名表/结构表 的槽内，
  而该槽已被对应定长模块收录 → 同一片 ROM 区域被两个模块重复覆盖。

对每个 scan 条目：
  - 起点落入哪些定长表的 [start, end]（按槽对齐判断）
  - 该槽的 (地址) 是否已存在于定长模块的 entries 中
统计并抽样打印。

用法: python scripts/research/ruby/texts_11_scan_intrude.py
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
OUT = ROOT / "work" / "_probe" / "texts_scan_intrude.json"


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

    # 定长表（stride/struct）的真实占用区间，按槽展开
    tables = []
    for name, m in mods.items():
        if m.get("type") not in ("stride", "struct"):
            continue
        r = m.get("read") or {}
        start = to_int(m.get("start"))
        end = to_int(m.get("end"))
        stride = r.get("stride") or r.get("entry_size")
        no = int(r.get("name_offset") or 0)
        if not (start and end and stride):
            continue
        n = (end - start + 1) // stride
        slots = []
        for k in range(n):
            base = start + k * stride
            slots.append((base + no, base + stride - 1))
        tables.append({"name": name, "slots": slots,
                       "addr_set": {(a, b) for a, b in slots}})

    scan_mods = [n for n, m in mods.items() if m.get("type") == "scan"]
    print(f"scan 模块: {scan_mods}")
    print(f"定长表: {[t['name'] for t in tables]}\n")

    for sm in scan_mods:
        print("=" * 112)
        print(f"scan 模块 {sm}：条目落入定长表槽的情况")
        print("=" * 112)
        hit_by_table = Counter()
        samples = defaultdict(list)
        for e in by_mod.get(sm, []):
            a = to_int(e.get("address"))
            if a is None:
                continue
            off = a - 0x08000000 if a >= 0x08000000 else a
            for t in tables:
                for lo, hi in t["slots"]:
                    if lo <= off <= hi:
                        hit_by_table[t["name"]] += 1
                        if len(samples[t["name"]]) < 5:
                            # 该槽是否也被定长模块收录
                            dup = any(to_int(x.get("address")) == 0x08000000 + lo
                                      for x in by_mod.get(t["name"], []))
                            samples[t["name"]].append(
                                (off, e.get("original") or "", dup))
                        break
        if not hit_by_table:
            print("  无条目落入任何定长表槽 → 与定长表无区域重复")
        else:
            for tn, c in hit_by_table.most_common():
                print(f"  落入 [{tn}] 的条目: {c}")
                for off, orig, dup in samples[tn]:
                    print(f"     0x{off:06X} dup_slot={dup}  {orig[:46]!r}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
