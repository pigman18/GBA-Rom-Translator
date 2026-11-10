#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对比产物 ROM 里道具名新表 vs 原表，逐字段核对。

用途：定位「列表里出现乱码行」到底是哪个字段读错。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ORG = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
OUT = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
ASM = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook" / "gen" / "table_data.asm"

OLD_BASE = 0x39A648
OLD_STRIDE = 40
NEW_STRIDE = 48

# 生成器里声明的 field_map
FIELD_MAP = [
    (0x0A, 0x12, 2), (0x0C, 0x14, 2), (0x0E, 0x16, 1), (0x0F, 0x17, 1),
    (0x10, 0x24, 4), (0x14, 0x18, 1), (0x15, 0x19, 1), (0x16, 0x1A, 1),
    (0x17, 0x1B, 1), (0x18, 0x20, 4), (0x1C, 0x1C, 2), (0x20, 0x28, 4),
]


def new_base() -> int | None:
    if not ASM.is_file():
        return None
    src = ASM.read_text(encoding="utf-8")
    m = re.search(r"\.org\s+(0x[0-9A-Fa-f]+)\s*\n\.align\s+4\s*\nTblItemNames:", src)
    return int(m.group(1), 16) - 0x08000000 if m else None


def main() -> int:
    org = ORG.read_bytes()
    out = OUT.read_bytes()
    nb = new_base()
    if nb is None:
        print("[ERR] 找不到 TblItemNames 地址")
        return 3
    print(f"原表 0x{OLD_BASE + 0x08000000:08X} stride {OLD_STRIDE}")
    print(f"新表 0x{nb + 0x08000000:08X} stride {NEW_STRIDE}\n")

    for idx in (0, 1, 2, 3, 9, 10):
        oe = OLD_BASE + idx * OLD_STRIDE
        ne = nb + idx * NEW_STRIDE
        print(f"=== entry[{idx}] ===")
        print(f"  原 +00..17: {org[oe:oe + 24].hex(' ')}")
        print(f"  新 +00..17: {out[ne:ne + 24].hex(' ')}")
        bad = 0
        for oo, no, w in FIELD_MAP:
            a = org[oe + oo:oe + oo + w]
            b = out[ne + no:ne + no + w]
            if a != b:
                print(f"  ★ +0x{no:02X}(旧{oo:02X}) want={a.hex()} got={b.hex()}")
                bad += 1
        if not bad:
            print("  字段全部一致")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
