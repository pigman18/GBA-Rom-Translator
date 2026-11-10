#!/usr/bin/env python3
"""按日版符号表地址反汇编函数（不靠美版源码推测）。

用法：
    python scripts/research/ruby/jp_disasm.py GetSpeciesName
    python scripts/research/ruby/jp_disasm.py 0x0803B48C 0x4a
    python scripts/research/ruby/jp_disasm.py --sym SpeciesName   # 搜符号
"""
from __future__ import annotations

import re
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
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
SYM = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "symbols" / "pokeruby_jp.sym"

GBA = 0x08000000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)


def load_syms() -> list[tuple[int, int, str, str]]:
    out = []
    for line in SYM.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        try:
            addr = int(parts[0], 16)
            size = int(parts[2], 16)
        except ValueError:
            continue
        out.append((addr, size, parts[3], line))
    return out


def find_sym(syms, name: str):
    if name.lower().startswith("0x"):
        addr = int(name, 16)
        for a, sz, n, raw in syms:
            if a == addr:
                return a, sz, n, raw
        return addr, 0, "?", ""
    hits = [s for s in syms if s[2].lower() == name.lower()]
    if not hits:
        hits = [s for s in syms if name.lower() in s[2].lower()]
    return hits[0] if hits else None


def main() -> int:
    rom = ROM.read_bytes()
    syms = load_syms()

    if len(sys.argv) < 2:
        print("用法: jp_disasm.py <符号名|地址> [长度]")
        return 1

    if sys.argv[1] == "--sym":
        kw = sys.argv[2] if len(sys.argv) > 2 else ""
        for a, sz, n, _ in syms:
            if kw.lower() in n.lower():
                print(f"  0x{a:08X}  size=0x{sz:<6X} {n}")
        return 0

    target = sys.argv[1]
    hit = find_sym(syms, target)
    if hit is None:
        print(f"找不到符号: {target}")
        return 1

    addr, size, name, raw = hit
    if len(sys.argv) > 2:
        size = int(sys.argv[2], 0)

    off = addr - GBA
    if size <= 0:
        size = 0x80

    print("=" * 78)
    print(f"{name}  0x{addr:08X}  size=0x{size:X}  ({size} 字节)")
    if raw:
        print(f"符号行: {raw.strip()[:110]}")
    print("=" * 78)

    for ins in md.disasm(rom[off:off + size], addr):
        mark = ""
        if ins.mnemonic == "ldr" and "pc" in ins.op_str:
            # 解析字面量
            try:
                imm = int(ins.op_str.split("#")[1].rstrip("]"), 0)
            except (IndexError, ValueError):
                imm = 0
            lit = ((ins.address + 4) & ~3) + imm
            if lit + 4 <= len(rom):
                v = struct.unpack_from("<I", rom, lit)[0]
                mark = f"   ; literal@0x{lit:06X} = 0x{v:08X}"
        print(f"  0x{ins.address:08X}: {ins.bytes.hex(' '):<9} "
              f"{ins.mnemonic:<8} {ins.op_str}{mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
