#!/usr/bin/env python3
"""最终验证：auto_layout 用真实译文自动判定每张表的处理方案。

期望输出（依据 a2_table_fit.py 实测）：
  道具名        FIXED             281/281 塞得下
  图鉴分类名    FIXED             343/343
  树果名        FIXED
  招式名        SWAP_STRIDE       8→32（×4，2的幂）
  特性名        SWAP_STRIDE       8→32（×4，2的幂）
  属性名        SWAP_STRIDE_HARD  5→20（×4，非2幂）
  秘密基地装饰名 SWAP_STRIDE_HARD  28→56（×2，非2幂）

用法：
    python scripts/research/ruby/a2_final_plan.py
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
OUT = ROOT / "work" / "_probe" / "a2_final_plan.json"

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

EXPECT = {
    "道具名": "fixed",
    "图鉴分类名": "fixed",
    "树果名": "fixed",
    "招式名": "swap_stride",
    "特性名": "swap_stride",
    "属性名": "swap_hard",
    "秘密基地装饰名": "swap_hard",
}


def main() -> int:
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path
    from meowth.table_expand import encode_body
    from meowth.auto_layout import build_layout_plan, report, MODE_DESC

    cm = Charmap(charmap_path=get_charmap_path("POKEMON_RUBY_AXVJ00"),
                 target_lang="zh-Hans")
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    entries = [e for e in (d.get("entries") or [])
               if e.get("type") == "replace" and e.get("phrase_code") is not None]

    # body_of：给出一条的编码长度
    def body_of(c):
        for e in entries:
            try:
                a = int(str(e.get("address") or "0x0").replace("0x", ""), 16)
            except ValueError:
                continue
            if a >= 0x08000000:
                a -= 0x08000000
            if a == c.addr:
                return encode_body(cm, e.get("translated") or "")
        return b""

    print(f"条目 {len(entries):,}，跑自动划分…\n")
    plan = build_layout_plan(rom, entries, TABLES, body_of=body_of)
    print(report(plan))

    print()
    print("=== 定长表方案判定（对照期望）===")
    print(f"{'表':<16} {'条数':>5} {'模式':<14} {'stride':>12} {'字面量':>6} {'塞得下':>7} {'超出':>5} 期望")
    ok = 0
    for g in plan.table_groups:
        exp = EXPECT.get(g.table_name, "-")
        got = g.mode.value
        mark = "✅" if got == exp or exp == "-" else "❌"
        if got == exp:
            ok += 1
        stride_s = f"{g.stride}→{g.new_stride}" if g.stride_mult > 1 else str(g.stride)
        print(f"{g.table_name:<16} {len(g.entries):>5} {got:<14} {stride_s:>12} "
              f"{g.n_literals:>6} {g.fitted:>7} {g.overflow:>5} {exp:<14} {mark}")

    print()
    print(f"判定吻合: {ok} / {len([k for k in EXPECT])}")

    # 汇总收益
    fixed_n = sum(len(g.entries) for g in plan.table_groups if g.mode.value == "fixed")
    swap_n = sum(len(g.entries) for g in plan.table_groups
                 if g.mode.value.startswith("swap"))
    print()
    print("=== 收益汇总 ===")
    print(f"  FIXED（零机器码改动）: {fixed_n} 条")
    print(f"  SWAP_STRIDE（改移位）: {swap_n} 条")
    print(f"  合计可消灭 F980:      {fixed_n + swap_n} 条")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "table_groups": [
            {"table": g.table_name, "n": len(g.entries), "mode": g.mode.value,
             "stride": g.stride, "new_stride": g.new_stride,
             "mult": g.stride_mult, "literals": g.n_literals,
             "fitted": g.fitted, "overflow": g.overflow}
            for g in plan.table_groups
        ],
        "summary": plan.summary(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
