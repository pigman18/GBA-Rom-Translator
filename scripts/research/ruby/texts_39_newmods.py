#!/usr/bin/env python3
"""texts_39: 三个新模块的候选验证（建模块前先测）。

要建：
  1. UI-详情页     stride_ptr @0x397330  n=7   （收编存档的 7 条）
  2. 词库-0x3B2    scan  0x3B2000..0x3B2A00    （67 条特性名副本，插在剧情前抢归属）
  3. 战斗提示      scan  0x3DA000..0x3DC000    （36 条正常战斗提示，从剧情/UI 移出）

本脚本只做「能不能收到预期条数」的验证，不写文件。

用法: python scripts/research/ruby/texts_39_newmods.py
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

    print("=" * 112)
    print("1) UI-详情页：stride_ptr @0x397330，stride=4，试 n=7/8")
    print("=" * 112)
    for end in ("0x397348", "0x39734c"):
        m = {"id": "UI-详情页", "type": "stride_ptr", "start": "0x397330",
             "end": end, "read": {"stride": 4}}
        out = TP.extract_module(rom, m, "AXVJ", filters=None)
        print(f"  end={end}: {len(out)} 条")
        for e in out:
            print(f"      {e['address']} {e['original']!r}")

    print()
    print("=" * 112)
    print("2) 词库-0x3B2：scan 0x3B2000..0x3B2A00，试不同 filter")
    print("=" * 112)
    # 不带 filter（最宽松）
    m = {"id": "词库-0x3B2", "type": "scan",
         "start": "0x3B2000", "end": "0x3B29FF"}
    out = TP.extract_module(rom, m, "AXVJ", filters=None)
    print(f"  无 filter: {len(out)} 条")
    for e in out[:10]:
        print(f"      {e['address']} {e['original'][:30]!r}")
    print(f"      ... 共 {len(out)}")

    # 带 min_byte_length
    m2 = dict(m)
    m2["min_byte_length"] = 2
    out2 = TP.extract_module(rom, m2, "AXVJ", filters=None)
    print(f"\n  min_byte_length=2: {len(out2)} 条")

    print()
    print("=" * 112)
    print("3) 战斗提示：scan 0x3DA000..0x3DC000")
    print("=" * 112)
    m3 = {"id": "战斗提示", "type": "scan",
          "start": "0x3DA000", "end": "0x3DBFFF"}
    out3 = TP.extract_module(rom, m3, "AXVJ", filters=None)
    print(f"  无 filter: {len(out3)} 条")
    for e in out3[:6]:
        print(f"      {e['address']} {e['original'][:44]!r}")
    print(f"      ... 共 {len(out3)}")

    print()
    print("=" * 112)
    print("对照：这三个区段目前在文件里的归属")
    print("=" * 112)
    zones = [("UI详情", 0x3EA787, 0x3EA7AA), ("词库0x3B2", 0x3B2000, 0x3B2A00),
             ("战斗提示", 0x3DA000, 0x3DC000)]
    by_mod: dict[str, int] = defaultdict(int)
    for label, lo, hi in zones:
        c = defaultdict(int)
        for e in d["entries"]:
            a = to_int(e["address"]) - 0x08000000
            if lo <= a < hi:
                c[e["module"]] += 1
        print(f"  {label:<12} {dict(c)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
