#!/usr/bin/env python3
"""texts_36: 第4步 —— 三个全 ROM scan 模块的区间重划（含零损失验证）。

核心事实（texts_28 已证）：scan 模块只搜 start..end 区间，
把区间从 0x0..0xFFFFFF 收窄到「覆盖全部现有条目」的范围，抽取结果 0 变化。

实测各模块条目真实范围：
  UI界面   0x14DDC7 .. 0x3F1ACA
  剧情     0x145D92 .. 0x7EF450
  补漏剧情 0x107700 .. 0x7FDF6C

重划方案（按 ROM 区段语义，不改变条目归属）：
  1. 剧情        -> 0x100000..0x800000（脚本正文全段；原 0x0..0xFFFFFF 的前 1MB 是 ROM 头/码，无文本）
  2. 补漏剧情    -> 0x100000..0x800000（同上；它的条目分布与剧情同区，靠 require_pointer 区分）
  3. UI界面      -> 0x100000..0x800000（同上）
  4. 新增 词库-0x3B2：把 0x3B2000..0x3B2A00 从剧情切出去（67 条零指针的特性名副本）
     并加 address_filter 把这段从剧情排除

先只做 1..3（纯收窄，零风险），4 需要 filter 改动，单独验证。

用法: python scripts/research/ruby/texts_36_reband.py
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

sys.path.insert(0, str(ROOT / "src"))
import util.texts_patcher as TP  # noqa: E402


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


def off_of(e) -> int:
    a = to_int(e.get("address")) or 0
    return a - 0x08000000 if a >= 0x08000000 else a


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods = d["modules"]
    by_mod: dict[str, list] = defaultdict(list)
    for e in d["entries"]:
        by_mod[e.get("module")].append(e)

    print("=" * 112)
    print("各 scan 模块条目真实范围 vs 建议新区间")
    print("=" * 112)
    NEW = {}
    for n in ("UI界面", "剧情", "补漏剧情"):
        a = sorted(off_of(e) for e in by_mod[n])
        lo, hi = a[0], a[-1]
        # 新区间：向前/向后各留 0x1000 余量，但不超出 ROM
        ns = max(0, (lo - 0x1000) & ~0xFFF)
        ne = min(0x7FFFFF, ((hi + 0x1000) | 0xFFF))
        NEW[n] = (ns, ne)
        print(f"  {n:<10} 现有条目 0x{lo:06X}..0x{hi:06X}  "
              f"→ 建议 0x{ns:06X}..0x{ne:06X}")

    print()
    print("=" * 112)
    print("零损失验证：区间收窄后重抽，条目集合是否完全相同")
    print("=" * 112)
    all_ok = True
    for n, (ns, ne) in NEW.items():
        trial = dict(mods[n])
        trial["id"] = n
        trial["start"] = f"0x{ns:X}"
        trial["end"] = f"0x{ne:X}"
        out = TP.extract_module(rom, trial, "AXVJ", filters=trial.get("filters"))
        cur = {off_of(e) for e in by_mod[n]}
        new = {off_of(e) for e in out}
        same = cur == new
        all_ok &= same
        print(f"  {n:<10} 现有 {len(cur):>5}  重抽 {len(new):>5}  "
              f"差 {len(cur ^ new):>3}  {'✅ 完全一致' if same else '❌ 有差异'}")
        if not same and (cur - new):
            print(f"      会丢: {[hex(x) for x in sorted(cur - new)[:6]]}")

    print()
    print("=" * 112)
    print("结论")
    print("=" * 112)
    if all_ok:
        print("  三个 scan 模块可以安全收窄区间：条目零变化，但消除了")
        print("  「声明覆盖整片 ROM」的结构问题。")
    else:
        print("  有模块收窄会丢条目，需调整余量后再定。")

    out_p = ROOT / "work" / "_probe" / "texts_reband.json"
    out_p.write_text(json.dumps(
        {n: {"start": f"0x{v[0]:X}", "end": f"0x{v[1]:X}"} for n, v in NEW.items()},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {out_p}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
