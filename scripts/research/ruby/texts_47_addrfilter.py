#!/usr/bin/env python3
"""texts_47: 用 address_filter 验证「区间切分」是否可行（替代局部 scan）。

texts_44/45 证明：局部 scan 因串起点错位不可行。
但 address_filter 是**在整段扫描之后**按地址判定，不改变串边界。

思路：
  新模块 = scan(整段 0x144000..0x7F0FFF) + address_filter{区间} filter:false(仅保留)
  → 串边界与剧情一致，只按地址筛掉区间外的

验证目标：
  词库-0x3B2  0x3B2000..0x3B2A00  应正好 68 条（剧情现有）
  战斗提示    0x3DA000..0x3DC000  应正好 388 条

用法: python scripts/research/ruby/texts_47_addrfilter.py
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

    ZONES = {
        "词库-0x3B2": (0x3B2000, 0x3B2A00),
        "战斗提示": (0x3DA000, 0x3DC000),
    }

    for zname, (lo, hi) in ZONES.items():
        target = {off_of(e) for e in d["entries"] if lo <= off_of(e) < hi}
        print()
        print("=" * 112)
        print(f"{zname}  0x{lo:06X}..0x{hi:06X}   文件现有 {len(target)} 条")
        print("=" * 112)

        # 新模块 = 剧情同款主filter + fallback + address_filter(仅保留区间)
        addr_f = [{
            "id": "addr_only_zone",
            "type": "address_filter",
            "filter": False,          # false = 只保留命中
            "value": {"start": f"0x{lo:X}", "end": f"0x{hi:X}"},
        }]

        variants = {
            "剧情同款filter+fallback + addr_only": (main_f, fb_f + addr_f),
            "裸 + addr_only": (None, addr_f),
            "剧情主 + addr_only": (main_f, addr_f),
        }
        for vname, (mf, ff) in variants.items():
            m = {"id": zname, "type": "scan",
                 "start": "0x144000", "end": "0x7F0FFF"}
            if ff:
                m["fallback_filters"] = ff
            try:
                out = TP.extract_module(rom, m, "AXVJ", ptr_index=ptr_index,
                                        filters=mf)
            except Exception as exc:  # noqa: BLE001
                print(f"  {vname:<38} 异常 {exc}")
                continue
            got = {off_of(e) for e in out}
            inter = got & target
            prec = len(inter) / len(got) if got else 0
            rec = len(inter) / len(target) if target else 0
            print(f"  {vname:<38} 收到 {len(got):>4}  命中 {len(inter):>4}  "
                  f"精确 {prec:>5.0%}  覆盖 {rec:>5.0%}  Δ={len(got)-len(target):+d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
