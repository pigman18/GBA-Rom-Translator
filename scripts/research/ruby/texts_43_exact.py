#!/usr/bin/env python3
"""texts_43: 正确复现「剧情 filter + fallback」组合，找新模块的精确等价定义。

texts_42 的错：只传 fallback_filters、不传主 filters，导致四变体结果相同。
真实语义（extract_scan）：先过 filters，命中的候选被丢弃；剩下再交 fallback_filters。
所以剧情 = 主 story_pointer_filter + fallback 四个。

本脚本验证：新模块沿用「剧情同款主filters + 同款fallback_filters + 收窄区间」，
能否在 0x3B2 / 0x3DA 区段精确复现文件里的归属条数。

用法: python scripts/research/ruby/texts_43_exact.py
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
    print("剧情主 filters:", [f.get("id") for f in main_f])
    print("剧情 fallback :", [f.get("id") for f in fb_f])

    ZONES = {"词库-0x3B2": (0x3B2000, 0x3B29FF),
             "战斗提示": (0x3DA000, 0x3DBFFF)}

    for zname, (lo, hi) in ZONES.items():
        target = {off_of(e) for e in d["entries"] if lo <= off_of(e) <= hi}
        print()
        print("=" * 112)
        print(f"{zname}  0x{lo:06X}..0x{hi:06X}   文件现有 {len(target)} 条")
        print("=" * 112)

        trials = {
            "主filter+fallback(剧情同款)": (main_f, fb_f),
            "仅主filter": (main_f, None),
            "仅fallback": (None, fb_f),
            "全裸": (None, None),
        }
        for tname, (mf, ff) in trials.items():
            m = {"id": zname, "type": "scan",
                 "start": f"0x{lo:X}", "end": f"0x{hi:X}"}
            if ff is not None:
                m["fallback_filters"] = ff
            try:
                out = TP.extract_module(rom, m, "AXVJ", ptr_index=ptr_index,
                                        filters=mf)
            except Exception as exc:  # noqa: BLE001
                print(f"  {tname:<28} 异常 {exc}")
                continue
            got = {off_of(e) for e in out}
            inter = got & target
            prec = len(inter) / len(got) if got else 0
            rec = len(inter) / len(target) if target else 0
            delta = len(got) - len(target)
            print(f"  {tname:<28} 收到 {len(got):>4}  命中 {len(inter):>4}  "
                  f"精确 {prec:>5.0%}  覆盖 {rec:>5.0%}  Δ={delta:+d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
