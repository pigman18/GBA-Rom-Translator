#!/usr/bin/env python3
"""验证：道具名 14 个站点，修正函数边界后各站点求出的来源指令。

期望：每个站点的来源指令都在**自己函数内**。
  0x0A538E → 应在 0x0A538C（同函数，ldr 前）
  0x0A53A2 → 应在 0x0A53B0（同函数，ldr 后）

用法：
    python scripts/research/ruby/check_item_fixed.py
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
sys.path.insert(0, str(ROOT / "src"))

ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"


def main() -> int:
    from meowth.thumb_symexec import solve_site, find_function_start
    from meowth.table_stride import find_ldrs

    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    rom = ROM.read_bytes()

    ldrs = find_ldrs(rom, 0x39A648)
    print(f"道具名 {len(ldrs)} 站点\n")
    print(f"{'ldr':>10} {'入口':>10} {'K':>5} {'来源':>10} {'相对':>6}  指令")
    print("-" * 72)
    for ldr in ldrs:
        entry = find_function_start(rom, ldr, limit=256)
        r = solve_site(rom, ldr)
        if r.insn_off is None:
            print(f"0x{ldr:06X} 0x{entry:06X} {str(r.stride):>5} "
                  f"{'—':>10} {'—':>6}  {r.reason}")
            continue
        ins = list(md.disasm(rom[r.insn_off:r.insn_off + 2], r.insn_off))
        txt = f"{ins[0].mnemonic} {ins[0].op_str}" if ins else "?"
        rel = r.insn_off - ldr
        ok = "✅" if entry <= r.insn_off <= ldr + 48 else "❌ 跨函数"
        print(f"0x{ldr:06X} 0x{entry:06X} {r.stride:>5} "
              f"0x{r.insn_off:06X} {rel:>+6}  {txt}  {ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
