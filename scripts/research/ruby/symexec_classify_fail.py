#!/usr/bin/env python3
"""对全部失败站点做根因归类（不猜，逐条实测）。

判据：
  A. BASE+const 丢失：窗口内出现「对 BASE 寄存器做 adds/subs 立即数」
  B. 线性扫描穿越数据：从入口线性扫到 ldr 的途中遇到 bx/bxns 等终止符
  C. 其它：窗口内没出现上述特征

用法：
    python scripts/research/ruby/symexec_classify_fail.py
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
    gba = base + 0x08000000
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
            if ((off + 4) & ~3) + (hw & 0xFF) * 4 == lit:
                if off not in seen:
                    seen.add(off)
                    ldrs.append(off)
                break
    return sorted(ldrs)


def classify(rom: bytes, ldr: int) -> tuple[str, str]:
    from meowth.thumb_symexec import solve_site, find_function_start, decode, BASE

    entry = find_function_start(rom, ldr, limit=256)
    hi = min(len(rom) - 1, ldr + 96)

    # 模拟一遍，记录「BASE 寄存器遇到加立即数」与「终止符」
    regs: dict[int, object] = {i: None for i in range(16)}
    base_plus: list[str] = []
    terminator: list[str] = []

    for ins in md.disasm(rom[entry:hi], entry):
        a = ins.address
        mn, ops = ins.mnemonic, ins.op_str
        if mn == "ldr" and "pc" in ops:
            rd = ops.split(",")[0].strip()
            regs[int(rd[1:])] = "BASE"
            continue
        if mn in ("adds", "add", "subs", "sub") and "#" in ops:
            parts = [p.strip() for p in ops.split(",")]
            src = parts[0] if len(parts) == 2 else parts[1]
            dst = parts[0]
            if src.startswith("r") and regs.get(int(src[1:])) == "BASE":
                base_plus.append(f"0x{a:06X} {mn} {ops}")
                if dst.startswith("r"):
                    regs[int(dst[1:])] = "LOST"
                continue
        if mn in ("bx", "bxns", "blx"):
            terminator.append(f"0x{a:06X} {mn} {ops}")
            break
        if mn in ("pop",) and "pc" in ops:
            terminator.append(f"0x{a:06X} pop {ops}")
            break

    if base_plus:
        return "A", base_plus[0]
    if terminator:
        return "B", terminator[0]
    return "C", ""


def main() -> int:
    rom = ROM_PATH.read_bytes()
    from meowth.thumb_symexec import solve_site

    counts: dict[str, int] = {}
    print(f"{'表':<16} {'ldr':>9} {'K':>5} {'根因':>4}  证据")
    print("-" * 88)
    for name, base, stride in TABLES:
        for ldr in find_ldrs(rom, base):
            r = solve_site(rom, ldr)
            if r.stride is not None:
                continue
            kind, ev = classify(rom, ldr)
            counts[kind] = counts.get(kind, 0) + 1
            tag = {"A": "A BASE+const 丢失",
                   "B": "B 线性扫描撞终止符",
                   "C": "C 其它"}[kind]
            print(f"{name:<16} 0x{ldr:06X} {'?':>5} {kind:>4}  {ev}")
    print("-" * 88)
    print(f"归类统计: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
