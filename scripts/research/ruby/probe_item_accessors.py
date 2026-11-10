#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""道具表 14 个访问函数的字段偏移全貌。

目的：决定 stride 40→48（元数据后移 8B）后，每个函数怎么改。

## 已探明的两种写法

A) 直接偏移：`adds r1,r1,r4` 后 `ldrb r0,[r1,#0x14]`
   → 字段偏移 +8 后可能超过 5 位立即数范围（0..31），需 trampoline。

B) 先调基址：`ldr r4,[pc]` … `adds r4,#0x10` … `adds r1,r1,r4` 再 `ldr r0,[r1]`
   → 改 pc 字面量（base → base+8）即可，或改 `adds r4` 立即数。

本脚本把每处归类并给出改法。
"""
from __future__ import annotations

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
TABLE = 0x0839A648
SHIFT = 8


def main() -> int:
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    rom = ROM.read_bytes()

    pat = struct.pack("<I", TABLE)
    sites = []
    i = rom.find(pat)
    while i != -1:
        sites.append(i)
        i = rom.find(pat, i + 1)

    print(f"道具表 0x{TABLE:08X}  字面量站点 {len(sites)}  元数据后移 {SHIFT}B")
    print("=" * 92)
    for s in sites:
        st = s
        for back in range(2, 0x40, 2):
            if (rom[s - back] & 0xFF) == 0xB5:
                st = s - back
                break
        ins = list(md.disasm(rom[st:st + 0x30], st + 0x08000000))

        r4_adj = None
        field = None
        field_ins = None
        for x in ins:
            if x.mnemonic == "adds" and x.op_str.startswith("r4, #"):
                r4_adj = (x.address, x.op_str)
            if x.mnemonic in ("ldr", "ldrb", "ldrh") and x.op_str.startswith("r0, [r1"):
                field = x.op_str
                field_ins = x

        kind = "B(base+adj)" if r4_adj else "A(direct)"
        detail = ""
        if r4_adj:
            imm = int(r4_adj[1].split("#")[1], 16)
            detail = f"adds r4,#0x{imm:X} → 改 #0x{imm + SHIFT:X}"
        elif field_ins is not None:
            op = field_ins.op_str
            if "#0x" in op:
                imm = int(op.split("#")[1].rstrip("]"), 16)
                new = imm + SHIFT
                maxv = 31 if field_ins.mnemonic in ("ldr", "ldrb") else 62
                detail = (f"偏移 0x{imm:X}→0x{new:X}"
                          + ("（可原地改）" if new <= maxv else "（超限，需 trampoline）"))
            else:
                detail = "偏移 0（ldr [r1]）→ 需 +8，用 adds r1,#8 或 trampoline"
        print(f"0x{st + 0x08000000:08X} {kind:<12} 读 {field}  |  {detail}")
    print()
    print("结论：")
    print("  · kind B 的站点只要改 'adds r4,#imm' 的立即数（+8），一条指令搞定；")
    print("  · kind A 且新偏移 ≤ 上限的，改 ldr/ldrb 立即数即可；")
    print("  · 其余必须 trampoline。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
