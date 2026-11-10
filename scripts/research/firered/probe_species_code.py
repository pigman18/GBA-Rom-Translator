#!/usr/bin/env python3
"""火红宝可梦名：0x71F444 被 31 处代码引用，查它怎么被读。

关键问题：这 31 处引用是怎么把「物种 ID」变成「中文名」的？
若代码改成读 0x71F444 而不是原版 gSpeciesNames，说明是「换表」；
若两者都读，说明有分支。

用法：
    python scripts/research/firered/probe_species_code.py
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
ORIG = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"

GBA_BASE = 0x08000000
CODE_END = 0x200000
BASE_ZH = 0x71F444

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)


def find_refs(rom: bytes, gba: int, limit: int = 60) -> list[int]:
    needle = struct.pack("<I", gba)
    out, s = [], 0
    while len(out) < limit:
        i = rom.find(needle, s)
        if i < 0:
            break
        out.append(i)
        s = i + 1
    return out


def main() -> int:
    a = ORIG.read_bytes()
    b = ZH.read_bytes()

    for tag, rom in (("原版", a), ("汉化", b)):
        refs = find_refs(rom, BASE_ZH + GBA_BASE)
        code_refs = [r for r in refs if r < CODE_END]
        print(f"=== {tag}：0x{BASE_ZH:06X} 引用 {len(refs)}，代码段 {len(code_refs)} ===")
        for r in code_refs[:2]:
            print(f"  字面量 @ 0x{r:06X}  前 8B: {rom[max(0,r-8):r].hex(' ')}")
            # 找引用它的 ldr
            ldr = None
            for off in range(max(0, r - 4096), r, 2):
                hw = struct.unpack_from("<H", rom, off)[0]
                if (hw & 0xF800) != 0x4800:
                    continue
                imm = (hw & 0xFF) * 4
                if ((off + 4) & ~3) + imm == r:
                    ldr = off
                    break
            if ldr is not None:
                print(f"    ← ldr @ 0x{ldr:X}，上下文:")
                code = rom[ldr:ldr + 64]
                for ins in md.disasm(code, ldr):
                    if ins.address - ldr > 48:
                        break
                    print(f"       0x{ins.address:06X}: {ins.mnemonic:<8}{ins.op_str}")
            print()

    # 原版物种名表：找 gSpeciesNames 等价位置
    print("=== 原版 412 项 × 11 字节 的候选名字表 ===")
    for base in range(0x300000, 0x500000, 4):
        ok = 0
        for k in range(30):
            p = base + k * 11 + 10
            if p < len(a) and a[p] == 0xFF:
                ok += 1
        if ok >= 29:
            print(f"  候选 0x{base:06X}（前 30 项末字节 FF {ok}/30）")
            print(f"    原版: {a[base:base+44].hex(' ')}")
            print(f"    汉化: {b[base:base+44].hex(' ')}")
            d = sum(1 for x, y in zip(a[base:base+11*30], b[base:base+11*30]) if x != y)
            print(f"    前 30 项差异 {d}/{11*30} ({d/(11*30):.0%})")
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
