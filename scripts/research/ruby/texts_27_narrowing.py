#!/usr/bin/env python3
"""texts_27: 第4步方案验证 —— 收窄三个全 ROM scan 模块的区间，会不会丢条目。

思路：不改 filter、只改 start/end（方案 A），然后真跑抽取，
与当前 texts.json 的条目集合逐模块比对，量化「收窄代价」。

同时验证：0x3B2xxx 词库区、0x3E9xxx 资源区 能否按区间切出去。

用法: python scripts/research/ruby/texts_27_narrowing.py
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


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods = d["modules"]
    by_mod: dict[str, list] = defaultdict(list)
    for e in d["entries"]:
        by_mod[e.get("module")].append(e)

    print("=" * 112)
    print("1) 现状：三模块各自条目数")
    print("=" * 112)
    for n in ("UI界面", "剧情", "补漏剧情"):
        print(f"  {n:<10} {len(by_mod[n]):>5}")

    print()
    print("=" * 112)
    print("2) 把条目落点画成「现有条目集合」，用于算收窄代价")
    print("=" * 112)
    cur = {n: {to_int(e.get("address")) - 0x08000000 for e in by_mod[n]}
           for n in ("UI界面", "剧情", "补漏剧情")}
    for n, s in cur.items():
        print(f"  {n:<10} 唯一地址 {len(s)}")

    print()
    print("=" * 112)
    print("3) 候选切分：0x3B2xxx 词库区、高位 0x400000+ 归属谁")
    print("=" * 112)
    for n in ("UI界面", "剧情", "补漏剧情"):
        z1 = sum(1 for a in cur[n] if 0x3B2000 <= a < 0x3B2A00)
        z2 = sum(1 for a in cur[n] if a >= 0x400000)
        z3 = sum(1 for a in cur[n] if 0x3DC000 <= a < 0x3EB000)
        print(f"  {n:<10} 0x3B2词库={z1:>4}  高位>=0x400000={z2:>4}  "
              f"UI字库0x3DC-0x3EB={z3:>4}")

    print()
    print("=" * 112)
    print("4) 试跑：剧情 收窄到 [0x100000, 0x3F2000]（排除高位）")
    print("=" * 112)
    trial = dict(mods["剧情"])
    trial["id"] = "剧情"
    trial["start"] = "0x100000"
    trial["end"] = "0x3F2000"
    out = TP.extract_module(rom, trial, "AXVJ",
                            filters=trial.get("filters"))
    lost = cur["剧情"] - {to_int(e["address"]) - 0x08000000 for e in out}
    print(f"  现有 {len(cur['剧情'])} -> 试跑 {len(out)}，会丢 {len(lost)}")
    if lost:
        ls = sorted(lost)[:10]
        print(f"  丢失样本: {[hex(x) for x in ls]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
