#!/usr/bin/env python3
"""验证 auto_layout.py 能独立复现 A1 的归属判定。

对照基准（A1 用 7 支脚本人工分析得出的结论）：
  FIXED_TABLE   1,178
  PTR_ARRAY     1,034
  CODE_LITERAL    298
  FREE_TEXT       259
  NO_PTR        4,270
  NO_PTR_BLOCKED  105

本脚本用 auto_layout 跑一遍，看是否吻合。

用法：
    python scripts/research/ruby/a2_autolayout_verify.py
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
sys.path.insert(0, str(ROOT / "src"))

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"

# A1 实测基准
BASELINE = {
    "FIXED_TABLE": 1178,
    "PTR_ARRAY": 1034,
    "CODE_LITERAL": 298,
    "FREE_TEXT": 259,
    "NO_PTR": 4270,
    "NO_PTR_BLOCKED": 105,
}

# 已知定长表几何（ROM 实测）
TABLES = {
    "招式名":         {"base": 0x1CACFC, "stride": 8,  "name_offset": 0, "n": 354},
    "特性名":         {"base": 0x1CBC44, "stride": 8,  "name_offset": 0, "n": 77},
    "属性名":         {"base": 0x1CBB0C, "stride": 5,  "name_offset": 0, "n": 18},
    "宝可梦名":       {"base": 0x1CA354, "stride": 6,  "name_offset": 0, "n": 412},
    "道具名":         {"base": 0x39A648, "stride": 40, "name_offset": 0, "n": 348},
    "图鉴分类名":     {"base": 0x38474C, "stride": 28, "name_offset": 6, "n": 386},
    "秘密基地装饰名": {"base": 0x3C2A44, "stride": 28, "name_offset": 13, "n": 120},
    "树果名":         {"base": 0x3A1034, "stride": 56, "name_offset": 0, "n": 21},
}


def main() -> int:
    from meowth.auto_layout import build_layout_plan, report

    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = [e for e in (d.get("entries") or [])
               if e.get("type") == "replace" and e.get("phrase_code") is not None]

    print(f"待分类 F980 条目: {len(entries):,}")
    print("跑 auto_layout …\n")

    plan = build_layout_plan(rom, entries, TABLES)
    print(report(plan))
    print()

    # 对照基准
    s = plan.summary()
    got = {
        "FIXED_TABLE": s["table_entries"],
        "PTR_ARRAY": s["array_entries"],
        "CODE_LITERAL": s["code_literals"],
        "FREE_TEXT": s["free_text"],
        "NO_PTR": s["no_ptr"],
    }
    print("=== 与 A1 基准对照 ===")
    print(f"  {'容器':<16} {'auto_layout':>12} {'A1 基准':>10} {'差异':>8}")
    for k, base_v in BASELINE.items():
        if k == "NO_PTR_BLOCKED":
            continue
        g = got.get(k, 0)
        diff = g - base_v
        mark = "✅" if abs(diff) <= max(5, base_v * 0.05) else "⚠️"
        print(f"  {k:<16} {g:>12,} {base_v:>10,} {diff:>+8,}  {mark}")

    print()
    print(f"  NO_PTR_BLOCKED 在 auto_layout 里并入 NO_PTR（不区分）")
    print()

    # 定长表详情
    print("=== 定长表分组与模式选择 ===")
    print(f"  {'表':<16} {'条数':>5} {'cap':>5} {'模式':<10} {'塞得下':>7} {'超出':>5}")
    for g in plan.table_groups:
        print(f"  {g.table_name:<16} {len(g.entries):>5} {g.cap:>5} "
              f"{g.mode.value:<10} {g.fitted:>7} {g.overflow:>5}")

    print()
    print("=== 指针数组（前 8）===")
    for g in plan.array_groups[:8]:
        print(f"  数组 @0x{g.base:06X}  {len(g.entries)} 条 / {g.n_slots} 槽")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
