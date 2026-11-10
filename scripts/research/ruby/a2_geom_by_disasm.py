#!/usr/bin/env python3
"""用「反汇编 + 指针表」双重判据，确定 6 张定长表的真实几何。

吸取的教训（三轮都栽在同一处）：
  统计法（FF 填充/元数据众数）都不可靠 —— 名字长度本来就不固定。

正确做法：
  1. 找代码里 index×stride + base 的乘法指令
  2. 反汇编看：
     - 是否 ldrb 循环到 FF/00（变长名字）
     - 还是固定偏移 ldr/ldrh（定宽字段）
  3. 名字区宽度 = 从乘法后第一个字节读取到「下一个字段」的偏移

对每个表同时报告：
  - 代码基址（反汇编用的字面量）
  - 名字区在条目内的偏移与宽度
  - 该表是否其实是指针表（像性格名）

用法：
    python scripts/research/ruby/a2_geom_by_disasm.py
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


def find_ldr(rom: bytes, lit: int, back: int = 4096) -> list[int]:
    out = []
    for off in range(max(0, lit - back), lit, 2):
        hw = struct.unpack_from("<H", rom, off)[0]
        if (hw & 0xF800) != 0x4800:
            continue
        imm = (hw & 0xFF) * 4
        if ((off + 4) & ~3) + imm == lit:
            out.append(off)
    return out


def main() -> int:
    rom = ROM_PATH.read_bytes()

    for name, base, stride in TABLES:
        print(f"\n{'=' * 70}")
        print(f"=== {name}  base=0x{base:06X} stride={stride} ===")

        # 找引用基址的 ldr
        lit_sites = []
        needle = struct.pack("<I", base + GBA_BASE)
        s = 0
        while True:
            i = rom.find(needle, s)
            if i < 0:
                break
            if i % 4 == 0:
                lit_sites.append(i)
            s = i + 1

        print(f"  对齐字面量 {len(lit_sites)} 处")

        if not lit_sites:
            print("  ❌ 无字面量，无法反汇编")
            continue

        # 反汇编第一个站点的引用处
        shown = 0
        for lit in lit_sites:
            ldrs = find_ldr(rom, lit)
            if not ldrs:
                continue
            ldr = ldrs[0]
            print(f"  字面量 0x{lit:06X} ← ldr @0x{ldr:X}")
            print(f"    ldr 前 20 字节（找乘法）：")
            lo = max(0, ldr - 20)
            for ins in md.disasm(rom[lo:ldr + 32], lo):
                mark = ""
                if ins.mnemonic in ("lsls", "lsl", "muls", "adds", "add"):
                    mark = "  ←"
                if ins.address == ldr:
                    mark = "  ← 加载基址"
                print(f"      0x{ins.address:06X}: {ins.mnemonic:<8}{ins.op_str}{mark}")
                if ins.address - ldr > 16:
                    break
            shown += 1
            if shown >= 1:
                break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
