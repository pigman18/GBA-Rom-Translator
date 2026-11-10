#!/usr/bin/env python3
"""道具名：代码到底怎么取名字的？——反汇编 0x0A538E 附近的 ldr。

已知：
  - 结构：base=0x39A658, entry_size=40, name@+0x18，6/6 合法
  - 但 0x0839A658 无字面量；0x0839A648 有 14 处（全 ldr）

看 0x0A538E 的 ldr 上下文：
  09 0c 88 00 | 40 18 | c0 00 | 02 49 | 40 18 | 02 bc | 08 47 | 00 00 | 48 a6 39 08
                              └─ ldr r1,[pc,#8] → 字面量 0x0839A648

指令序列解读：
  09 0c    lsrs r1, r1, #0x10
  88 00    lsls r0, r0, #2
  40 18    adds r0, r0, r1
  c0 00    lsls r0, r0, #3      ← ×8
  02 49    ldr r1, [pc, #8]     ← 0x0839A648
  40 18    adds r0, r0, r1
  ...
即 index 计算 = (x*4 + y) * 8 + 0x39A648 = 0x39A648 + idx*8

**这是 stride=8 的表，不是 stride=40！**

用法：
    python scripts/research/ruby/a2_item_code.py
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


def ldr_refs(rom: bytes, lit: int, back: int = 4096) -> list[int]:
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

    for lit in (0x0A5398, 0x0A53BC):
        ldrs = ldr_refs(rom, lit)
        if not ldrs:
            continue
        ldr = ldrs[0]
        print(f"=== 字面量 0x{lit:06X}  ← ldr 0x{ldr:X} ===")
        # 往前反汇编 40 字节，往后 40 字节
        lo = max(0, ldr - 40)
        code = rom[lo:ldr + 48]
        for ins in md.disasm(code, lo):
            mark = ""
            if ins.address == ldr:
                mark = "   ← 加载基址 0x0839A648"
            if ins.mnemonic in ("lsls", "lsl"):
                mark += "  [移位]"
            if ins.mnemonic in ("adds", "add") and mark == "":
                mark = "  [加]"
            print(f"  0x{ins.address:06X}: {ins.mnemonic:<8}{ins.op_str}{mark}")
        print()

    # 验证 stride=8 假设：0x39A648 + i*8 处是什么
    print("=== 验证：0x39A648 + i*8 ===")
    for i in range(8):
        off = 0x39A648 + i * 8
        seg = rom[off:off + 8]
        v = struct.unpack_from("<I", rom, off)[0]
        is_ptr = GBA_BASE <= v < 0x0A000000
        print(f"  i={i} 0x{off:06X}: {seg.hex(' ')}   u32=0x{v:08X}"
              + (f" → 0x{v-GBA_BASE:06X}" if is_ptr else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
