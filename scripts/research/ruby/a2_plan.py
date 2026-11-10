#!/usr/bin/env python3
"""A2 准备：各容器的具体清单与批量处理参数。

归属已知的 5,654 条，按容器整理出「可批量执行的单位」：
  FIXED_TABLE  1,178 → 按表分组，每表一次改动
  PTR_ARRAY    1,034 → 按数组分组，每数组一次改动
  CODE_LITERAL   298 → 逐条（但可批量改字面量）
  FREE_TEXT      259 → 逐条 relocate

本脚本算出：
  1. PTR_ARRAY 的数组分组（哪些条目在同一个数组）
  2. 每个数组的基址、元素数、跨度
  3. CODE_LITERAL 的字面量站点清单

用法：
    python scripts/research/ruby/a2_plan.py
"""
from __future__ import annotations

import json
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
OWN = ROOT / "work" / "_probe" / "a1_ownership.json"
OUT = ROOT / "work" / "_probe" / "a2_plan.json"
GBA_BASE = 0x08000000


def main() -> int:
    rom = ROM_PATH.read_bytes()
    own = json.loads(OWN.read_text(encoding="utf-8"))

    # ---- 1. PTR_ARRAY 数组分组 ----
    ptr_arr = own.get("PTR_ARRAY") or []
    print(f"PTR_ARRAY 条目 {len(ptr_arr):,}\n")

    # 按「站点所在的连续指针串」分组
    sites = []
    for r in ptr_arr:
        s = int(r["site"].replace("0x", ""), 16)
        sites.append((s, r))
    sites.sort()

    arrays = []
    cur = []
    prev = None
    for s, r in sites:
        if prev is not None and s == prev + 4:
            cur.append((s, r))
        else:
            if cur:
                arrays.append(cur)
            cur = [(s, r)]
        prev = s
    if cur:
        arrays.append(cur)

    print("=== 指针数组分组 ===")
    print(f"  共 {len(arrays):,} 个数组")
    sizes = Counter(len(a) for a in arrays)
    print("  元素数分布（前 8）:")
    for n, c in sizes.most_common(8):
        print(f"    {n:>3} 元素: {c:>4} 个数组")

    # 大数组详情
    arrays.sort(key=lambda a: -len(a))
    print()
    print("=== 最大的 10 个数组 ===")
    array_info = []
    for arr in arrays[:10]:
        base = arr[0][0]
        tgts = []
        for s, r in arr:
            tgts.append(int(r["addr"].replace("0x", ""), 16))
        span = max(tgts) - min(tgts) if tgts else 0
        # 数组前面的字节（判断是否有表头）
        pre = rom[max(0, base - 8):base]
        array_info.append({
            "base": f"0x{base:06X}", "n": len(arr),
            "span": span, "pre": pre.hex(" "),
        })
        print(f"  数组 @0x{base:06X}  {len(arr)} 元素  跨度 0x{span:X}")
        print(f"    前面 8B: {pre.hex(' ')}")

    # ---- 2. CODE_LITERAL 字面量站点 ----
    code_lit = own.get("CODE_LITERAL") or []
    print()
    print(f"=== CODE_LITERAL {len(code_lit):,} 条 ===")
    # 按 ldr 位置所在区段聚合
    zones = Counter()
    for r in code_lit:
        ldr = int(r.get("ldr", "0x0").replace("0x", ""), 16) if r.get("ldr") else 0
        zones[ldr >> 12] += 1
    print("  按 4KB 区段分布（前 10）:")
    for z, c in zones.most_common(10):
        print(f"    0x{z << 12:06X}: {c}")

    # ---- 3. FIXED_TABLE 按表分组 ----
    fixed = own.get("FIXED_TABLE") or []
    print()
    print(f"=== FIXED_TABLE {len(fixed):,} 条 ===")
    by_tbl = Counter(r.get("container") for r in fixed)
    for t, c in by_tbl.most_common():
        # 找该表的几何
        sample = next((r for r in fixed if r.get("container") == t), None)
        print(f"  {t:<16} {c:>5} 条  基址 {sample.get('table_base') if sample else '?'}  "
              f"stride {sample.get('stride') if sample else '?'}")

    # 保存
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "arrays": array_info,
        "n_arrays": len(arrays),
        "code_literal_zones": {f"0x{k << 12:06X}": v for k, v in zones.most_common(20)},
        "fixed_table": dict(by_tbl),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n计划 → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
