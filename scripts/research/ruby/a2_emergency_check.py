#!/usr/bin/env python3
"""紧急排查：招式名/道具名的 stride 改动是否只改了一处乘法。

怀疑：
  招式名有 43 处字面量引用，道具名有 14 处。
  每处引用都有自己的 index×stride 乘法序列。
  我在 a2_gen_final_patch.py 里**每张表只改了一处** lsls！

若其他站点的乘法仍是旧 stride，就会读到错误位置 → 招式名空白、背包黑屏。

用法：
    python scripts/research/ruby/a2_emergency_check.py
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
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
GBA_BASE = 0x08000000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

# 已被我改过的表（基址, 旧stride, 新stride）
TABLES = [
    ("招式名",         0x1CACFC, 8,  32),
    ("特性名",         0x1CBC44, 8,  32),
    ("属性名",         0x1CBB0C, 5,  17),
    ("道具名",         0x39A648, 40, 80),
    ("图鉴分类名",     0x38474C, 28, 56),
    ("秘密基地装饰名", 0x3C2A44, 28, 56),
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


def find_mul_before(rom: bytes, ldr: int, window: int = 24) -> list[str]:
    """找 ldr 之前的乘法指令。"""
    lo = max(0, ldr - window)
    found = []
    for ins in md.disasm(rom[lo:ldr], lo):
        if ins.mnemonic in ("lsls", "lsl", "muls", "adds", "subs"):
            found.append(f"0x{ins.address:06X}:{ins.mnemonic} {ins.op_str}")
    return found


def main() -> int:
    rom = ROM.read_bytes()

    for name, base, old_s, new_s in TABLES:
        gba = base + GBA_BASE
        # 找所有字面量站点
        needle = struct.pack("<I", gba)
        sites = []
        s = 0
        while True:
            i = rom.find(needle, s)
            if i < 0:
                break
            if i % 4 == 0:
                sites.append(i)
            s = i + 1

        print(f"\n{'=' * 74}")
        print(f"=== {name}  base=0x{base:06X}  stride {old_s}→{new_s} ===")
        print(f"  字面量站点 {len(sites)} 处")

        # 每处站点找引用它的 ldr，再看前面的乘法
        n_ldr = 0
        mul_sites = []
        for lit in sites:
            for ldr in find_ldr(rom, lit):
                n_ldr += 1
                muls = find_mul_before(rom, ldr)
                if muls:
                    mul_sites.append((ldr, muls))
                break   # 每处只取第一个 ldr

        print(f"  其中被 ldr 引用 {n_ldr} 处，前面有乘法的 {len(mul_sites)} 处")
        if mul_sites:
            print(f"  乘法站点（每处都需改！）:")
            for ldr, muls in mul_sites[:8]:
                print(f"    ldr@0x{ldr:06X}: " + " | ".join(muls[-3:]))
            if len(mul_sites) > 8:
                print(f"    … 另 {len(mul_sites) - 8} 处")

    print()
    print("=" * 74)
    print("=== 结论 ===")
    print("  若某表的「乘法站点」> 1，而 patch 只改了一处，")
    print("  则其他站点仍用旧 stride → 读错位置 → 空白/黑屏。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
