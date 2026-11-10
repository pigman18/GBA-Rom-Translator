#!/usr/bin/env python3
"""A 方案可行性调查：指针数组需要「idx×4 + 解引用」，能否实现？

思路对比：
  现状：addr = base + idx×stride + name_off → 直接当文本地址用
  目标：addr = base + idx×4 → ldr [addr] → 得到文本地址

关键问题：
  1. 原代码算完地址后做什么（传打印？直接读字节？）
  2. 计算链里有没有空间插入一条 ldr
  3. 若 stride 恰好能改成 4（2 的幂因子 - log2(stride/4)），只需改立即数吗？

先看招式名最典型的那个站点：0x02B53A。

用法：
    python scripts/research/ruby/a_plan_feasibility.py
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

# 各表最典型的站点（ldr 加载基址的位置）
SITES = [
    ("招式名",         0x02B53A, 8),
    ("特性名",         0x09C6C4, 8),
    ("属性名",         0x02B6B0, 5),
    ("道具名",         0x0A538E, 40),
    ("图鉴分类名",     0x08C1D6, 28),
    ("秘密基地装饰名", 0x0AF2C8, 28),
]


def main() -> int:
    rom = ROM.read_bytes()

    for name, ldr, stride in SITES:
        print("=" * 76)
        print(f"=== {name}  ldr@0x{ldr:06X}  stride={stride} ===")
        print("=" * 76)

        lo = max(0, ldr - 16)
        insns = list(md.disasm(rom[lo:ldr + 24], lo))
        for ins in insns:
            mark = ""
            if ins.address == ldr:
                mark = "  ★ ldr 基址"
            elif ins.mnemonic in ("lsls", "lsrs", "adds", "subs", "ldr", "ldrh",
                                  "ldrb", "bl", "blx"):
                mark = "  ←"
            print(f"  0x{ins.address:06X}: {ins.mnemonic:<8}{ins.op_str}{mark}")

        # 判断：ldr 之后紧跟的指令是什么
        after = [i for i in insns if i.address > ldr][:3]
        print(f"\n  ldr 之后 3 条:")
        for ins in after:
            print(f"    0x{ins.address:06X}: {ins.mnemonic:<8}{ins.op_str}")
        print()

    # 关键分析：stride → 4 需要什么
    print("=" * 76)
    print("=== stride → 4 的改动需求 ===")
    print("=" * 76)
    print(f"{'表':<16} {'旧':>4} {'新':>3} {'倍数':>5} {'移位变化':>8} {'需插 ldr':>8}")
    print("-" * 60)
    for name, _ldr, stride in SITES:
        ratio = stride / 4
        if ratio == int(ratio) and (int(ratio) & (int(ratio) - 1)) == 0:
            delta = int(ratio).bit_length() - 1
            shift = f"-{delta}"
        else:
            shift = "非2幂"
        print(f"{name:<16} {stride:>4} {4:>3} {ratio:>5.1f} {shift:>8} {'是':>8}")

    print()
    print("说明：")
    print("  stride=8  → 4 是移位 -1，但**仍需插入解引用 ldr**")
    print("  stride=28/40 不是 4 的 2 幂倍，无法靠改移位实现")
    print()
    print("⇒ 结论：A 方案不能只改立即数，必须插入 ldr 指令")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
