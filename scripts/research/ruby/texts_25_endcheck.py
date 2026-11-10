#!/usr/bin/env python3
"""texts_25: 按「end 含末字节」逐一复核所有定长表的末槽（第4步前置）。

已踩过两次坑（树果名/性格名），这里把全部定长表按同一方法核一遍：
  对每张表，计算当前 end 下的槽数，并检查：
    L1 末槽是否是合法文本槽（能读到 eos、内容非空）
    L2 末槽之后紧邻的字节是否「已经是下一张表/指针区」
    L3 end 放大/缩小一格 stride 时条数如何变化
给出每张表的「末槽是否完整」结论，以及是否需要动 end。

用法: python scripts/research/ruby/texts_25_endcheck.py
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
from meowth.jp_pcs import decode_pcs  # noqa: E402


def slot_text(rom: bytes, off: int, window: int, eos: int = 0xFF) -> str:
    lim = min(len(rom), off + window)
    for i in range(off, lim):
        if rom[i] == eos:
            return decode_pcs(rom[off:i + 1])
    return ""


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods = d["modules"]

    print("=" * 112)
    print("定长表末槽复核（end 含末字节）")
    print("=" * 112)

    for name, m in mods.items():
        if m.get("type") not in ("stride", "struct"):
            continue
        r = m.get("read") or {}
        s = int(m["start"], 16)
        e = int(m["end"], 16)
        st = r.get("stride") or r.get("entry_size")
        no = int(r.get("name_offset") or 0)
        eos = int(r.get("eos", 0xFF))
        slots = (e - s + 1) // st

        last_off = s + (slots - 1) * st + no
        last_t = slot_text(rom, last_off, st - no, eos)
        # 末槽之后
        after = s + slots * st
        after_bytes = rom[after:after + 8].hex(" ")
        # 放大一格 / 缩小一格
        slots_more = (e + st - 1 - s + 1) // st
        slots_less = (e - st - s + 1) // st
        more_t = slot_text(rom, s + slots * st + no, st - no, eos) if slots_more > slots else ""
        less_t = slot_text(rom, s + (slots_less - 1) * st + no, st - no, eos) if slots_less > 0 else ""

        print(f"\n--- {name}  0x{s:06X}..0x{e:06X} stride={st} name@+{no} "
              f"eos=0x{eos:02X}  slots={slots}")
        print(f"    末槽[{slots-1}] @0x{last_off:06X}: {last_t!r}")
        print(f"    末槽后 0x{after:06X}: {after_bytes}"
              f"  ← 若不是文本起点，说明 end 正好")
        if slots_more > slots:
            print(f"    若 end+1 格 -> {slots_more} 槽，多出的槽: {more_t!r}")
        if slots_less > 0 and slots_less < slots:
            print(f"    若 end-1 格 -> {slots_less} 槽，会丢掉: {less_t!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
