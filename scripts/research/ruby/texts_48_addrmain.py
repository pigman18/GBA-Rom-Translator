#!/usr/bin/env python3
"""texts_48: address_filter 的正确用法 —— 放主 filters 而非 fallback_filters。

texts_47 的错：把 address_filter 塞进 fallback_filters，导致主 filter 阶段
全部候选放行（7907/88854 条）。fallback 只在主 filter 拒绝后才用。

正确语义（extract_scan）：
  候选 → 主 filters：命中(exclude=true)即丢弃 → 剩余 → fallback_filters

要让 address_filter 起「只保留区间内」的作用，必须放**主 filters**，
且 filter=false（只保留命中）。但主 filters 里 story_pointer 也会拒绝无指针文本，
两个 filter 是 AND 关系（都要通过）——这正是我们要的：
  · story_pointer 保证是真剧情（或 fallback 补充）
  · address_filter 保证只在本区间

用法: python scripts/research/ruby/texts_48_addrmain.py
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
    ptr_index = TP._build_ptr_index(rom)
    story = d["modules"]["剧情"]
    main_f = TP.resolve_filters({"texts": {}}, story)
    fb_f = story.get("fallback_filters") or []

    ZONES = {"词库-0x3B2": (0x3B2000, 0x3B2A00),
             "战斗提示": (0x3DA000, 0x3DC000)}

    for zname, (lo, hi) in ZONES.items():
        target = {off_of(e) for e in d["entries"] if lo <= off_of(e) < hi}
        print()
        print("=" * 112)
        print(f"{zname}  0x{lo:06X}..0x{hi:06X}   文件现有 {len(target)} 条")
        print("=" * 112)

        addr_f = {"id": "addr_only_zone", "type": "address_filter",
                  "filter": False,
                  "value": {"start": f"0x{lo:X}", "end": f"0x{hi:X}"}}

        trials = {
            "剧情主+addr(主filters)": (main_f + [addr_f], None),
            "剧情主+addr + 剧情fallback": (main_f + [addr_f], fb_f),
            "裸+addr(主filters)": ([addr_f], None),
        }
        for tname, (mf, ff) in trials.items():
            m = {"id": zname, "type": "scan",
                 "start": "0x144000", "end": "0x7F0FFF"}
            if ff:
                m["fallback_filters"] = ff
            try:
                out = TP.extract_module(rom, m, "AXVJ", ptr_index=ptr_index,
                                        filters=mf)
            except Exception as exc:  # noqa: BLE001
                print(f"  {tname:<30} 异常 {exc}")
                continue
            got = {off_of(e) for e in out}
            inter = got & target
            prec = len(inter) / len(got) if got else 0
            rec = len(inter) / len(target) if target else 0
            print(f"  {tname:<30} 收到 {len(got):>5}  命中 {len(inter):>4}  "
                  f"精确 {prec:>5.0%}  覆盖 {rec:>5.0%}  Δ={len(got)-len(target):+d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
