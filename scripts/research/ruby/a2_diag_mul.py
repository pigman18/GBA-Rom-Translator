#!/usr/bin/env python3
"""诊断：为什么有站点找不到 stride 乘法？

现象：
  招式名 40 处，只找到 34 处，6 处报「找不到 stride 乘法」：
    0x06D656 / 0x06D900 / 0x06DF62 ...
  特性名 3 处，只找到 2 处：
    0x09C6C4（就是我之前改的那个）

这说明我的 `find_stride_shift` 判据太窄。

用法：
    python scripts/research/ruby/a2_diag_mul.py
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

# 报错的站点
CASES = [
    ("招式名", 0x06D656, 8),
    ("招式名", 0x06D900, 8),
    ("招式名", 0x06DF62, 8),
    ("特性名", 0x09C6C4, 8),
    ("特性名", 0x11C59C, 8),
    ("特性名", 0x11CAC6, 8),
]


def main() -> int:
    rom = ROM.read_bytes()

    for name, ldr, stride in CASES:
        print(f"\n=== {name} ldr@0x{ldr:06X} 旧stride={stride} ===")
        print(f"  往前 24 字节反汇编:")
        lo = max(0, ldr - 24)
        for ins in md.disasm(rom[lo:ldr + 8], lo):
            mark = ""
            if ins.address == ldr:
                mark = "  ← ldr 基址"
            elif ins.mnemonic in ("lsls", "lsl", "muls", "adds", "subs", "add"):
                mark = "  ←"
            print(f"    0x{ins.address:06X}: {ins.mnemonic:<8}{ins.op_str}{mark}")

    # 特别看 0x09C6C4 后面（这是原脚本改过的那个）
    print()
    print("=== 0x09C6C4 完整上下文（前后 40 字节）===")
    for r in range(0, 80, 16):
        off = 0x09C6B0 + r
        print(f"  0x{off:06X}: {rom[off:off + 16].hex(' ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
