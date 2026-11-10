#!/usr/bin/env python3
"""反汇编确认：定长名称表是靠 index*stride 硬算，还是读指针/表内地址。

这是「能否整表搬走」的最后一道判据：
  - index*stride 硬算（ldr rX,[pc,#n] 取基址 + 乘法/移位 + 相加）
      → 整表搬走可行（只改基址字面量），但 stride 不能变
  - 读表内地址 / 每项单独指针
      → 逐项搬走可行

做法：对每张表，在代码段找「持有基址字面量的 ldr」周围的反汇编，
看后续是 lsl/add（乘 stride）还是 ldr [rX]（读指针）。

用 capstone（若无则退化为十六进制 dump）。

用法：
    python scripts/research/ruby/probe_table_indexing.py
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

GBA_BASE = 0x08000000
CODE_END = 0x100000

# (名称, 真实基址, 配置 stride)
TABLES = [
    ("招式名", 0x1CACFC, 8),
    ("特性名", 0x1CBC44, 8),
    ("属性名", 0x1CBB0C, 5),
    ("道具名", 0x39A648, 40),
    ("图鉴分类名", 0x38474C, 28),
    ("秘密基地装饰名", 0x3C2A44, 28),
]

try:
    import capstone  # type: ignore
    HAVE_CS = True
except Exception:
    HAVE_CS = False


def literal_sites(rom: bytes, gba: int) -> list[int]:
    needle = struct.pack("<I", gba)
    out, start = [], 0
    while True:
        i = rom.find(needle, start)
        if i < 0:
            break
        if i % 4 == 0 and i < CODE_END:
            out.append(i)
        start = i + 1
    return out


def find_ldr(rom: bytes, lit_off: int, back: int = 1024) -> list[int]:
    """找引用该字面量的 thumb ldr 指令偏移。"""
    hits = []
    for off in range(max(0, lit_off - back), lit_off, 2):
        hw = struct.unpack_from("<H", rom, off)[0]
        if (hw & 0xF800) != 0x4800:
            continue
        imm = (hw & 0xFF) * 4
        if ((off + 4) & ~3) + imm == lit_off:
            hits.append(off)
    return hits


def thumb_insn_off(addr: int) -> int:
    return addr & 1


def main() -> int:
    rom = ROM.read_bytes()
    md = None
    if HAVE_CS:
        md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
        md.detail = False

    print(f"ROM {len(rom):,} B   capstone={'yes' if HAVE_CS else 'no（退化为 hex dump）'}\n")

    for name, base, stride in TABLES:
        sites = literal_sites(rom, base + GBA_BASE)
        print(f"=== {name} === 基址 0x{base:06X} stride={stride} 代码段字面量 {len(sites)}")

        if not sites:
            print("  无代码段字面量\n")
            continue

        shown = 0
        for lit in sites[:3]:
            ldrs = find_ldr(rom, lit)
            if not ldrs:
                continue
            for ldr in ldrs[:1]:
                print(f"  字面量 0x{lit:X}  ← ldr @ 0x{ldr:X}")
                start = ldr
                if md is not None:
                    code = rom[start:start + 40]
                    for insn in md.disasm(code, start):
                        mark = ""
                        if insn.mnemonic in ("lsl", "lsls", "add", "adds", "mul", "muls"):
                            mark = "   ← 索引计算"
                        if insn.mnemonic in ("ldr", "ldrb", "ldrh") and "r0," in insn.op_str:
                            pass
                        print(f"     0x{insn.address:06X}: {insn.mnemonic:<8}{insn.op_str}{mark}")
                        if insn.address - start > 28:
                            break
                else:
                    print("     " + rom[start:start + 32].hex(" "))
                print()
                shown += 1
        if shown == 0:
            print("  未找到引用该字面量的 ldr 指令")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
