#!/usr/bin/env python3
"""texts_20: 边界结论复核 —— 逐条验证文档里所有「建议改 start/end」的判据。

技能提醒的三条几何语义（都是最容易判错的）：
  G1 end 含末字节：条数 = (end - start + 1) // entry_size
  G2 name_offset 相对条目基址；名字出现在「表基址+偏移」是正常结构，
     不能据此判起点偏移（道具表第 0 项是占位符 "？？？" 时尤其如此）
  G3 指针表条目指向表外正文是其正常语义

对每个「我要建议修改」的模块，用两种几何各跑一遍真实抽取，比较哪个更自洽。

用法: python scripts/research/ruby/texts_20_boundary_recheck.py
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
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"

sys.path.insert(0, str(ROOT / "src"))
import util.texts_patcher as TP  # noqa: E402
from meowth.jp_pcs import decode_pcs  # noqa: E402


def slot_text(rom: bytes, off: int, window: int, eos: int = 0xFF) -> str:
    lim = min(len(rom), off + window)
    for i in range(off, lim):
        if rom[i] == eos:
            return decode_pcs(rom[off:i + 1])
    return ""


def run(mod: dict, rom: bytes) -> list[dict]:
    m = dict(mod)
    m.setdefault("id", mod.get("module"))
    return TP.extract_module(rom, m, "AXVJ", filters=None)


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods = d["modules"]
    by_mod: dict[str, list] = {}
    for e in d["entries"]:
        by_mod.setdefault(e.get("module"), []).append(e)

    print("=" * 112)
    print("G1/G2 复核一：道具名 —— 第 0 项到底是不是占位符？")
    print("=" * 112)
    start, es = 0x39A648, 40
    for i in range(3):
        off = start + i * es
        print(f"  index {i}: 0x{off:06X}  name@+0 -> {slot_text(rom, off, es)!r}")
    first_real = by_mod.get("道具名", [{}])[0]
    print(f"  texts.json 首条: {first_real.get('address')} {first_real.get('original')!r}")
    print(f"  表基址 0x{start:06X}，首条地址 0x{int(first_real.get('address'),16):X}，"
          f"差 {int(first_real.get('address'),16) - 0x08000000 - start}")
    print("  => 若 index 0 是 '？？？？？？？？' 占位，则 name@0 + 跳过占位符 才是正解，"
          "不需要 name_offset")
    print()

    print("=" * 112)
    print("G1 复核二：宝可梦名 —— end=0x1CACFB 是否本就给出 412 槽？")
    print("=" * 112)
    s, e, st = 0x1CA354, 0x1CACFB, 6
    n = (e - s + 1) // st
    print(f"  ({hex(e)}-{hex(s)}+1)//6 = {n} 槽（end 含末字节）")
    print(f"  末槽 index {n-1} @0x{s + (n-1)*st:06X} -> {slot_text(rom, s+(n-1)*st, st)!r}")
    print(f"  次末槽 index {n-2} @0x{s + (n-2)*st:06X} -> {slot_text(rom, s+(n-2)*st, st)!r}")
    lex = json.loads((ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" /
                      "lexicon" / "图鉴.json").read_text(encoding="utf-8"))
    tail = slot_text(rom, s + (n - 1) * st, st)
    print(f"  末槽 {tail!r} 在 图鉴.json 词表里？ {tail in lex}")
    print(f"  texts.json 宝可梦名条数: {len(by_mod.get('宝可梦名', []))}"
          f"（= {n} 槽 - 1 个 '？？？？？' 被 filter 跳过）")
    print()

    print("=" * 112)
    print("复核三：地点名 —— 0x3BECB7 之前是否真有完整地名？")
    print("=" * 112)
    print(f"  0x3BECB0 -> {slot_text(rom, 0x3BECB0, 16)!r}")
    print(f"  0x3BECB7 -> {slot_text(rom, 0x3BECB7, 16)!r}")
    locs = by_mod.get("地点名", [])
    print(f"  texts.json 首条: {locs[0].get('address')} {locs[0].get('original')!r}")
    print()

    print("=" * 112)
    print("复核四：训练家名 —— 0x1C4A10 首条是否真是碎片？")
    print("=" * 112)
    for off in (0x1C4A10, 0x1C4A1F):
        print(f"  0x{off:06X} -> {slot_text(rom, off, 24)!r}")
    tj = by_mod.get("训练家名", [])
    print(f"  texts.json 首条: {tj[0].get('address')} {tj[0].get('original')!r}")
    print()

    print("=" * 112)
    print("复核五：道具说明 —— 0x39A63F 尾条是什么？")
    print("=" * 112)
    di = by_mod.get("道具说明", [])
    print(f"  末条: {di[-1].get('address')} {di[-1].get('original')!r}")
    print(f"  其 raw: {di[-1].get('original_hex')}")
    print()

    print("=" * 112)
    print("复核六：用抽取器实测各候选几何的产出条数")
    print("=" * 112)
    cases = [
        ("道具名 现状(name_offset 无)", {"type": "struct", "start": "0x39a648",
                                       "end": "0x39dca7", "read": {"entry_size": 40}}),
        ("道具名 +name_offset=0x28", {"type": "struct", "start": "0x39a648",
                                     "end": "0x39dca7",
                                     "read": {"entry_size": 40, "name_offset": 0x28}}),
        ("宝可梦名 end=0x1CACFB", {"type": "stride", "start": "0x1ca354",
                                  "end": "0x1cacfb", "read": {"stride": 6}}),
        ("宝可梦名 end=0x1CACF5", {"type": "stride", "start": "0x1ca354",
                                  "end": "0x1cacf5", "read": {"stride": 6}}),
        ("树果名 stride=56(现状)", {"type": "struct", "start": "0x3a1050",
                                   "end": "0x3a14e8",
                                   "read": {"entry_size": 56, "name_offset": 0,
                                            "desc_ptr_offset": 12}}),
        ("树果名 stride=28", {"type": "struct", "start": "0x3a1050",
                              "end": "0x3a14e8",
                              "read": {"entry_size": 28, "name_offset": 0,
                                       "desc_ptr_offset": 0x10}}),
    ]
    for label, mod in cases:
        try:
            out = run(mod, rom)
            print(f"  {label:<28} -> {len(out):>4} 条")
        except Exception as exc:  # noqa: BLE001
            print(f"  {label:<28} -> 异常 {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
