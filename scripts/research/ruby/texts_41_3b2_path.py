#!/usr/bin/env python3
"""texts_41: 0x3B2 那 68 条的进入路径复盘 —— 反推可复现的认可条件。

texts_40 证伪了「新模块用指针类 filter 能抢到 0x3B2」：
该区段 75 条里只有 2 条有指针，任何指针 filter 只收到 1 条。

那剧情是怎么收到 68 条的？只有一个可能：**剧情走的是 fallback 通道**
（fallback_filters 里 dialogue_shape 允许 pointer_ok=false）。
但 texts_35 统计该区段 fallback 标记为 0……矛盾。

本脚本把这条查清楚：逐条打印 0x3B2 条目的 filter 相关字段，
并直接复跑「剧情模块」看它到底走哪条路。

用法: python scripts/research/ruby/texts_41_3b2_path.py
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
    return to_int(e.get("address")) - 0x08000000


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))

    z = [e for e in d["entries"]
         if 0x3B2000 <= off_of(e) < 0x3B2A00 and e["module"] == "剧情"]
    print("=" * 112)
    print(f"0x3B2 区段中归属「剧情」的 {len(z)} 条 —— 字段全貌")
    print("=" * 112)
    keys = set()
    for e in z:
        keys |= set(e.keys())
    print(f"  出现过的字段: {sorted(keys)}")
    print(f"  带 fallback 的: {sum(1 for e in z if 'fallback' in e)}")
    print(f"  带 is_pointer_based=True 的: {sum(1 for e in z if e.get('is_pointer_based'))}")
    print()
    for e in z[:6]:
        print(f"  {e['address']} {e['original'][:26]!r}")
        print(f"      ptr_src={e.get('pointer_sources')} "
              f"ptr_addr={e.get('pointer_addresses')} "
              f"is_ptr={e.get('is_pointer_based')} "
              f"fallback={e.get('fallback')}")

    print()
    print("=" * 112)
    print("复跑剧情模块，看它是否自己产出这 68 条")
    print("=" * 112)
    mod = dict(d["modules"]["剧情"])
    mod["id"] = "剧情"
    ptr_index = TP._build_ptr_index(rom)
    flt = TP.resolve_filters({"texts": {}}, mod)
    print(f"  生效 filters: {[f.get('id') for f in flt]}")
    print(f"  fallback_filters: "
          f"{[f.get('id') for f in (mod.get('fallback_filters') or [])]}")
    out = TP.extract_module(rom, mod, "AXVJ", ptr_index=ptr_index, filters=flt)
    got = {off_of(e) for e in out if 0x3B2000 <= off_of(e) < 0x3B2A00}
    print(f"  剧情复跑在 0x3B2 区段产出: {len(got)} 条")
    fb_marked = sum(1 for e in out
                    if 0x3B2000 <= off_of(e) < 0x3B2A00 and "fallback" in e)
    print(f"  其中带 fallback 标记: {fb_marked}")

    print()
    print("=" * 112)
    print("对照：剧情复跑在 0x3B2 的产出 vs 文件里的 68 条")
    print("=" * 112)
    file_set = {off_of(e) for e in z}
    print(f"  文件 {len(file_set)} 条，复跑 {len(got)} 条")
    print(f"  交集 {len(file_set & got)}，仅文件 {len(file_set - got)}，"
          f"仅复跑 {len(got - file_set)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
