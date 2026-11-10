#!/usr/bin/env python3
"""验证 table_stride 自动注入：6 张表的全部乘法站点是否都被找到。

对照基准（a2_emergency_check.py 实测的乘法站点数）：
  招式名         40
  道具名         14
  秘密基地装饰名 22
  图鉴分类名     5
  属性名         3
  特性名         3
  合计           87

用法：
    python scripts/research/ruby/a2_stride_auto_verify.py
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

# (表名, 基址, 旧stride, 新stride, 基准站点数)
TABLES = [
    ("招式名",         0x1CACFC, 8,  32, 40),
    ("特性名",         0x1CBC44, 8,  32, 3),
    ("属性名",         0x1CBB0C, 5,  17, 3),
    ("道具名",         0x39A648, 40, 80, 14),
    ("图鉴分类名",     0x38474C, 28, 56, 5),
    ("秘密基地装饰名", 0x3C2A44, 28, 56, 22),
]


def main() -> int:
    from meowth.table_stride import rewrite_table_stride, verify_stride_applied

    rom = ROM.read_bytes()

    print(f"{'表':<16} {'基准':>5} {'找到':>5} {'patch':>6} {'警告':>5} {'状态'}")
    print("-" * 62)

    total_expect = 0
    total_found = 0
    all_ok = True
    plans = []

    for name, base, old_s, new_s, expect in TABLES:
        r = rewrite_table_stride(
            rom, base, old_s, new_s,
            expect_min_sites=expect, dry_run=True,
        )
        total_expect += expect
        total_found += r.n_sites

        status = "✅" if (r.n_sites >= expect and not r.warnings) else "⚠️"
        if r.n_sites < expect or r.warnings:
            all_ok = False
        print(f"{name:<16} {expect:>5} {r.n_sites:>5} {len(r.patches):>6} "
              f"{len(r.warnings):>5} {status}")
        for w in r.warnings[:3]:
            print(f"    ⚠️ {w}")
        plans.append((name, r))

    print("-" * 62)
    print(f"{'合计':<16} {total_expect:>5} {total_found:>5}")

    # 详细看招式名（最容易漏的）
    print()
    print("=== 招式名 40 处站点明细（前 20）===")
    name, r = plans[0]
    for s in r.sites[:20]:
        print(f"  lsls@0x{s.insn_off:06X}  r{s.rd},r{s.rs},#{s.shift}  "
              f"← ldr@0x{s.ldr_off:06X}  literal@0x{s.literal_off:06X}")
    if r.n_sites > 20:
        print(f"  … 另 {r.n_sites - 20} 处")

    # 覆盖率
    print()
    print("=== 覆盖率 ===")
    for name, r in plans:
        expect = next(t[4] for t in TABLES if t[0] == name)
        rate = r.n_sites / expect if expect else 0
        print(f"  {name:<16} {r.n_sites}/{expect} = {rate:.0%}"
              + ("  ✅" if rate >= 1.0 else "  ⚠️ 有遗漏"))

    print()
    if all_ok:
        print("✅ 全部站点都被找到，可以生成自动注入")
        return 0
    print("⚠️ 有站点遗漏或警告，需先修正算法")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
