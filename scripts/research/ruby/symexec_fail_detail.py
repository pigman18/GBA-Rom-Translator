#!/usr/bin/env python3
"""列出全部求解失败/可疑站点，并定位数据流断点。

对每个失败站点：
  1. 追踪符号执行过程
  2. 找到「最后一次寄存器值从已知变为 UNKNOWN」的位置
  3. 输出该处指令 + 原因

用法：
    python scripts/research/ruby/symexec_fail_detail.py
"""
from __future__ import annotations

import struct
import sys
from collections import Counter
from pathlib import Path

import capstone

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
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


def find_ldrs(rom: bytes, base: int, back: int = 4096) -> list[int]:
    gba = base + GBA_BASE
    needle = struct.pack("<I", gba)
    lits, s = [], 0
    while True:
        i = rom.find(needle, s)
        if i < 0:
            break
        if i % 4 == 0:
            lits.append(i)
        s = i + 1
    ldrs, seen = [], set()
    for lit in lits:
        for off in range(max(0, lit - back), lit, 2):
            hw = struct.unpack_from("<H", rom, off)[0]
            if (hw & 0xF800) != 0x4800:
                continue
            imm = (hw & 0xFF) * 4
            if ((off + 4) & ~3) + imm == lit:
                if off not in seen:
                    seen.add(off)
                    ldrs.append(off)
                break
    return sorted(ldrs)


def main() -> int:
    from meowth.thumb_symexec import solve_site, find_function_start

    rom = ROM_PATH.read_bytes()

    # 收集所有失败站点
    fails = []
    for name, base, stride in TABLES:
        for ldr in find_ldrs(rom, base):
            r = solve_site(rom, ldr)
            if r.stride is None:
                fails.append((name, ldr, stride, r))

    print(f"=== 求解失败 {len(fails)} 处 ===\n")

    reason_cnt = Counter()
    for name, ldr, stride, r in fails:
        reason_cnt[r.reason] += 1

    print("失败原因分布:")
    for k, v in reason_cnt.most_common():
        print(f"  {k}: {v}")
    print()

    # 按表分组详看前几个
    by_table: dict[str, list] = {}
    for item in fails:
        by_table.setdefault(item[0], []).append(item)

    for name, items in by_table.items():
        print(f"\n{'=' * 74}")
        print(f"=== {name}  失败 {len(items)} 处 ===")
        print("=" * 74)
        for _n, ldr, stride, r in items[:3]:
            entry = find_function_start(rom, ldr, limit=256)
            print(f"\n--- ldr@0x{ldr:06X}  入口 0x{entry:06X}  "
                  f"stride={stride}  [{r.reason}] ---")
            # 打印 ldr 前后
            lo = max(0, ldr - 24)
            for ins in md.disasm(rom[lo:ldr + 16], lo):
                mark = ""
                if ins.address == ldr:
                    mark = "  ★基址"
                elif ins.mnemonic in ("lsls", "lsrs", "adds", "subs", "mov",
                                      "bl", "ldr", "ldrh", "ldrb"):
                    mark = "  ←"
                print(f"  0x{ins.address:06X}: {ins.mnemonic:<8}{ins.op_str}{mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
