#!/usr/bin/env python3
"""texts_45: 三个新模块的可行性终判 —— 哪个能建、哪个卡在哪。

结论汇总脚本，把 texts_39~44 的证据整理成一张表。

用法: python scripts/research/ruby/texts_45_verdict.py
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


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))

    print("=" * 112)
    print("模块 1：UI-详情页   stride_ptr @0x397330  —— 可建")
    print("=" * 112)
    m = {"id": "UI-详情页", "type": "stride_ptr", "start": "0x397330",
         "end": "0x39734C", "read": {"stride": 4}}
    out = TP.extract_module(rom, m, "AXVJ", filters=None)
    print(f"  抽取器实测: {len(out)} 条（目标 7）")
    for e in out:
        print(f"    {e['address']} {e['original']!r}")

    print()
    print("=" * 112)
    print("模块 2：词库-0x3B2  —— 卡住")
    print("=" * 112)
    print("  目标: 0x3B2000..0x3B2A00 的 68 条（现属剧情）")
    print("  障碍:")
    noptr = [e for e in d["entries"]
             if 0x3B2000 <= (to_int(e["address"]) - 0x08000000) < 0x3B2A00
             and not e.get("pointer_sources")]
    print(f"    a) 该区段 {len(noptr)} 条无指针 → 任何指针 filter 都只收到 1 条")
    print(f"    b) 裸 scan 收 129 条，其中只有 74 条是文件里的（精确率 57%）")
    print(f"       多出 55 条是 0x3B2000~0x3B20xx 的乱码碎片")
    print("    c) 剧情能收到这 68 条，靠的是 fallback 通道（dialogue_shape 允许无指针）")
    print("       但该通道对局部区间同样会放出碎片")
    print("  → 用 scan 圈区间不可行；需要「按地址白名单」的机制，现有抽取器没有。")

    print()
    print("=" * 112)
    print("模块 3：战斗提示  0x3DA000..0x3DC000  —— 部分可行")
    print("=" * 112)
    target = {to_int(e["address"]) - 0x08000000 for e in d["entries"]
              if 0x3DA000 <= (to_int(e["address"]) - 0x08000000) < 0x3DC000}
    print(f"  文件现有 {len(target)} 条（含 36 条 fallback + 大量普通条）")
    for label, s, e_ in (("裸扫", "0x3DA000", "0x3DBFFF"),):
        m = {"id": "战斗提示", "type": "scan", "start": s, "end": e_}
        out = TP.extract_module(rom, m, "AXVJ", filters=None)
        got = {to_int(x["address"]) - 0x08000000 for x in out}
        print(f"  {label}: 收到 {len(got)}，与文件交集 {len(got & target)}，"
              f"精确率 {len(got & target)/len(got):.0%}")
    print("  → 能收到大部分，但会多收 50 条、漏 49 条（串起点错位导致）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
