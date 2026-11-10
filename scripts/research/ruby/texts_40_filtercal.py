#!/usr/bin/env python3
"""texts_40: 新模块的 filter 校准 —— 用「现有归属」反推该带什么 filter。

texts_39 的教训：
  · UI-详情页   stride_ptr 天生精确（end=0x39734C 得 7 条）✅
  · 词库-0x3B2  裸 scan 得 129 条（含大量垃圾），目标是 68 条
  · 战斗提示    裸 scan 得 389 条，目标是 43 条正常文本

思路：新模块要收编的是「现在已被 剧情/UI界面 收进来的那些条目」，
所以新模块应当沿用**能收到它们的那些 filter**，而不是裸扫。

本脚本对每个候选 filter 组合，统计：
  · 收到多少条
  · 其中有多少是「当前已在文件里的条目」（precision）
  · 文件里该区段的条目有多少被覆盖（recall）

用法: python scripts/research/ruby/texts_40_filtercal.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from itertools import product
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


CANDIDATES = {
    "词库-0x3B2": (0x3B2000, 0x3B29FF),
    "战斗提示": (0x3DA000, 0x3DBFFF),
}

FILTER_SETS = {
    "裸扫(无filter)": None,
    "require_pointer": [{"id": "rp", "type": "require_pointer_filter", "value": True}],
    "story_pointer": [{"id": "sp", "type": "story_pointer_filter", "value": True}],
    "story_pointer+realref": [
        {"id": "sp", "type": "story_pointer_filter", "value": True},
        {"id": "rr", "type": "require_real_ref_filter", "value": True},
    ],
    "garbage_heuristic": [{"id": "gh", "type": "garbage_heuristic_filter", "value": True}],
    "min_len3": [{"id": "ml", "type": "min_byte_length_filter", "value": 3}],
    "min_len5": [{"id": "ml", "type": "min_byte_length_filter", "value": 5}],
}


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    ptr_index = TP._build_ptr_index(rom)

    cur_by_zone: dict[str, set[int]] = {}
    for name, (lo, hi) in CANDIDATES.items():
        cur_by_zone[name] = {
            off_of(e) for e in d["entries"] if lo <= off_of(e) <= hi
        }
        print(f"{name}: 文件里该区段共 {len(cur_by_zone[name])} 条")

    for name, (lo, hi) in CANDIDATES.items():
        print()
        print("=" * 112)
        print(f"{name}  0x{lo:06X}..0x{hi:06X}   目标 {len(cur_by_zone[name])} 条")
        print("=" * 112)
        target = cur_by_zone[name]
        print(f"  {'filter':<24} {'收到':>6} {'命中文件':>8} {'精确率':>7} "
              f"{'覆盖文件':>8} {'召回率':>7}")
        print("  " + "-" * 74)
        for fname, flt in FILTER_SETS.items():
            m = {"id": name, "type": "scan", "start": f"0x{lo:X}", "end": f"0x{hi:X}"}
            try:
                out = TP.extract_module(rom, m, "AXVJ", ptr_index=ptr_index,
                                        filters=flt)
            except Exception as exc:  # noqa: BLE001
                print(f"  {fname:<24} 异常 {exc}")
                continue
            got = {off_of(e) for e in out}
            inter = got & target
            prec = len(inter) / len(got) if got else 0
            rec = len(inter) / len(target) if target else 0
            print(f"  {fname:<24} {len(got):>6} {len(inter):>8} {prec:>6.0%} "
                  f"{len(inter):>8} {rec:>6.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
