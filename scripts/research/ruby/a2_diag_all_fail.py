#!/usr/bin/env python3
"""看清所有失败站点的真实形态，一次性搞清 stride 有多少种写法。

对每个失败的 (表, ldr) 打印完整反汇编，人工归纳形态。

用法：
    python scripts/research/ruby/a2_diag_all_fail.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import capstone

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
GBA_BASE = 0x08000000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

TABLES = [
    ("招式名",         0x1CACFC, 8),
    ("特性名",         0x1CBC44, 8),
    ("属性名",         0x1CBB0C, 5),
    ("道具名",         0x39A648, 40),
    ("图鉴分类名",     0x38474C, 28),
    ("秘密基地装饰名", 0x3C2A44, 28),
]


def main() -> int:
    from meowth.table_stride import (find_literal_sites, find_ldr_for_literal,
                                     find_stride_shift)
    rom = ROM.read_bytes()

    for name, base, stride in TABLES:
        lits = find_literal_sites(rom, base + GBA_BASE)
        fails = []
        for lit in lits:
            for ldr in find_ldr_for_literal(rom, lit):
                if find_stride_shift(rom, ldr, stride) is None:
                    fails.append((ldr, lit))

        if not fails:
            continue

        print(f"\n{'=' * 72}")
        print(f"=== {name}  stride={stride}  失败 {len(fails)}/{len(lits)} ===")
        for ldr, lit in fails[:4]:
            print(f"\n  --- ldr@0x{ldr:06X} ← literal 0x{lit:06X} ---")
            lo = max(0, ldr - 20)
            for ins in md.disasm(rom[lo:ldr + 10], lo):
                mark = ""
                if ins.address == ldr:
                    mark = "  ★ 基址 ldr"
                elif ins.mnemonic in ("lsls", "lsl", "muls", "adds", "subs"):
                    mark = "  ←"
                print(f"    0x{ins.address:06X}: {ins.mnemonic:<8}{ins.op_str}{mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
