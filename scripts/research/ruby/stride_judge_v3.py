#!/usr/bin/env python3
"""为什么「最后一条移位」不总是 stride 乘法？

问题：道具名 13 处最后一条是 `lsrs#16`，但那是 16 位截断，不是 stride。

看清道具名的完整计算链：
  0x0A5388: lsls r0, r1, #2      ← i*4
  0x0A538A: adds r0, r0, r1      ← i*4+i = i*5
  0x0A538C: lsls r0, r0, #3      ← i*5*8 = i*40  ★ 这才是 stride
  0x0A538E: ldr  r1, [pc, #8]    ← 基址

而另一个站点：
  0x0A53A2: ldr r4, [pc, #0x18]  ← 基址
  之前是 lsls#16 + lsrs#16       ← 那是 16 位截断，不是 stride！

⇒ 关键：**必须找「结果寄存器最终参与加基址」的那条移位**，
   而不是「ldr 前最后一条移位」。

真正的判据应该看 ldr **之后**的 adds 用的是哪个寄存器。

用法：
    python scripts/research/ruby/stride_judge_v3.py
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
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

CASES = [
    ("道具名 站点1 理想", 0x0A538E),
    ("道具名 站点2 问题", 0x0A53A2),
    ("招式名 理想", 0x02B53A),
    ("装饰名 问题", 0x0AF2C8),
]


def main() -> int:
    rom = ROM.read_bytes()

    for label, ldr in CASES:
        print("=" * 74)
        print(f"=== {label}  ldr@0x{ldr:06X} ===")
        print("=" * 74)
        lo = max(0, ldr - 16)
        for ins in md.disasm(rom[lo:ldr + 12], lo):
            mark = ""
            if ins.address == ldr:
                mark = "  ★ 基址"
            elif ins.mnemonic in ("lsls", "lsrs", "adds", "subs"):
                mark = "  ←"
            print(f"  0x{ins.address:06X}: {ins.mnemonic:<8}{ins.op_str}{mark}")
        print()

    print("=" * 74)
    print("=== 正确判据：从 ldr 之后的 adds 反推 ===")
    print("=" * 74)
    print()
    print("步骤：")
    print("  1. 解析 ldr 目标寄存器 rBase")
    print("  2. 找 ldr 之后最近的 `adds rX, rX, rBase`")
    print("     → rX 就是「最终地址」寄存器")
    print("  3. 从该 adds 往前，追踪 rX 的计算链")
    print("  4. 链里「最后一条作用于 rX 的移位」= stride 乘法")
    print()
    print("这样就能排除 `lsrs#16` 这类截断（它们不写入最终地址寄存器）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
