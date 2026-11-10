#!/usr/bin/env python3
"""导出所有失败站点的完整上下文，一次看清剩余问题。

当前 v3 覆盖率 74/92（80%）。剩余 18 处失败。
导出每处的反汇编（ldr 前后各 20 字节），归纳失败原因。

用法：
    python scripts/research/ruby/stride_fail_dump.py
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
    from meowth.table_stride import (find_ldrs, ldr_target_reg,
                                     find_addr_reg, trace_shift)
    rom = ROM.read_bytes()

    for name, base, stride in TABLES:
        ldrs = find_ldrs(rom, base)
        fails = []
        for ldr in ldrs:
            br = ldr_target_reg(rom, ldr)
            if br is None:
                fails.append((ldr, "非 ldr[pc]"))
                continue
            ar = find_addr_reg(rom, ldr, br)
            if ar is None:
                fails.append((ldr, f"无 adds rX,rX,r{br}"))
                continue
            st = trace_shift(rom, ldr, ar, stride)
            if st is None:
                fails.append((ldr, f"r{ar} 无 stride 移位"))
        if not fails:
            continue

        print(f"\n{'=' * 74}")
        print(f"=== {name}  stride={stride}  失败 {len(fails)}/{len(ldrs)} ===")
        print("=" * 74)
        for ldr, why in fails:
            print(f"\n--- ldr@0x{ldr:06X}  [{why}] ---")
            lo = max(0, ldr - 20)
            for ins in md.disasm(rom[lo:ldr + 20], lo):
                mark = ""
                if ins.address == ldr:
                    mark = "  ★ 基址"
                elif ins.mnemonic in ("lsls", "lsrs", "asrs", "adds", "subs"):
                    mark = "  ←"
                print(f"  0x{ins.address:06X}: {ins.mnemonic:<8}{ins.op_str}{mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
