#!/usr/bin/env python3
"""确认：道具名 14 个站点，是否真的有共用同一条 lsls 的情况？

如果两个站点共用一条乘法指令，那改一次就够（去重后 patch 数 < 站点数）。
但若它们本该各自有乘法，说明符号执行定位错了。

验证方法：对每个站点，看它「K=40 的来源指令」是否在 ldr 附近合理位置。

用法：
    python scripts/research/ruby/verify_item_sites.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
import capstone
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)


def main() -> int:
    from meowth.thumb_symexec import solve_site
    from meowth.table_stride import find_ldrs

    rom = ROM.read_bytes()
    BASE, STRIDE = 0x39A648, 40

    ldrs = find_ldrs(rom, BASE)
    print(f"道具名 ldr 站点 {len(ldrs)}\n")

    insn_map: dict[int, list[int]] = {}
    print(f"{'ldr':>10} {'K':>5} {'来源指令':>10} {'相对 ldr':>9}  指令")
    print("-" * 70)
    for ldr in ldrs:
        r = solve_site(rom, ldr)
        if r.insn_off is None:
            print(f"0x{ldr:06X} {r.stride} {'—':>10} {'—':>9}  {r.reason}")
            continue
        rel = r.insn_off - ldr
        ins = list(md.disasm(rom[r.insn_off:r.insn_off + 2], r.insn_off))
        txt = f"{ins[0].mnemonic} {ins[0].op_str}" if ins else "?"
        print(f"0x{ldr:06X} {r.stride:>5} 0x{r.insn_off:06X} {rel:>+9}  {txt}")
        insn_map.setdefault(r.insn_off, []).append(ldr)

    print()
    print("=== 共用同一指令的站点 ===")
    shared = 0
    for off_, users in insn_map.items():
        if len(users) > 1:
            shared += 1
            print(f"  0x{off_:06X} 被 {len(users)} 个站点共用: "
                  + ", ".join(f"0x{u:06X}" for u in users))
    if not shared:
        print("  无共用")
    print()
    print(f"唯一指令数 {len(insn_map)} / 站点数 {len(ldrs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
