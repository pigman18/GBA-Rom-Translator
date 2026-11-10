#!/usr/bin/env python3
"""确认道具名前两个站点是否共用乘法。

0x0A538E 和 0x0A53A2 都在 0x0A5378 这个函数里（0x0A5394 是 bx r1 返回）。
看它们的完整计算链。

用法：
    python scripts/research/ruby/check_item_pair.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import capstone

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"


def main() -> int:
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    rom = ROM.read_bytes()

    for lo, hi, label in (
        (0x0A5372, 0x0A5398, "函数1（含 ldr 0x0A538E）"),
        (0x0A5398, 0x0A53C0, "函数2（含 ldr 0x0A53A2）"),
    ):
        print(f"=== {label}  0x{lo:06X}..0x{hi:06X} ===")
        for ins in md.disasm(rom[lo:hi], lo):
            mark = ""
            if ins.address in (0x0A538E, 0x0A53A2):
                mark = "  ★ ldr 基址"
            elif ins.mnemonic in ("lsls", "adds", "bl", "bx", "pop", "push"):
                mark = "  ←"
            line = f"  0x{ins.address:06X}: {ins.mnemonic:<8}{ins.op_str}"
            print(line + mark)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
