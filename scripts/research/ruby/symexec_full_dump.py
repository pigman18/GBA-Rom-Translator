#!/usr/bin/env python3
"""把失败站点的【完整函数】反汇编出来，并叠上符号执行器的逐条状态。

目的：不再猜「大概是哪个指令没解码」，而是肉眼看清链断在哪一条。

用法：
    python scripts/research/ruby/symexec_full_dump.py            # 全部失败站点
    python scripts/research/ruby/symexec_full_dump.py 0x0A5432   # 指定站点
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

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
GBA_BASE = 0x08000000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
md.detail = False

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


def dump(rom: bytes, ldr: int, stride: int, table: str, fwd: int = 96) -> None:
    from meowth.thumb_symexec import solve_site, find_function_start

    entry = find_function_start(rom, ldr, limit=256)
    r = solve_site(rom, ldr)
    hi = min(len(rom) - 1, ldr + fwd)

    print()
    print("=" * 92)
    print(f"=== {table}  ldr@0x{ldr:06X}  入口 0x{entry:06X}  "
          f"旧stride={stride}  求解={'K=' + str(r.stride) if r.stride is not None else '失败'}")
    print(f"    求解原因: {r.reason}   (窗口 {entry:#x}..{hi:#x})")
    print("=" * 92)

    for ins in md.disasm(rom[entry:hi], entry):
        mark = ""
        if ins.address == ldr:
            mark = "  ★★★ 基址 ldr"
        elif ins.address == entry:
            mark = "  ← 函数入口"
        print(f"  0x{ins.address:06X}: {ins.bytes.hex(' '):<9} "
              f"{ins.mnemonic:<7} {ins.op_str}{mark}")

    # 额外：ldr 之后到 fwd 之外还有没有 add/移位（判断窗口是否太短）
    tail = md.disasm(rom[hi:hi + 48], hi)
    print(f"  ---- 窗口外后续（判断是否窗口太短）----")
    for ins in tail:
        print(f"  0x{ins.address:06X}: {ins.bytes.hex(' '):<9} "
              f"{ins.mnemonic:<7} {ins.op_str}")


def main() -> int:
    rom = ROM_PATH.read_bytes()
    only = int(sys.argv[1], 0) if len(sys.argv) > 1 else None

    if only is not None:
        hit = None
        for name, base, stride in TABLES:
            if only in find_ldrs(rom, base):
                hit = (name, stride)
                break
        dump(rom, only, hit[1] if hit else -1, hit[0] if hit else "?")
        return 0

    from meowth.thumb_symexec import solve_site

    n = 0
    for name, base, stride in TABLES:
        for ldr in find_ldrs(rom, base):
            if solve_site(rom, ldr).stride is None:
                dump(rom, ldr, stride, name)
                n += 1
    print(f"\n合计失败 {n} 处")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
