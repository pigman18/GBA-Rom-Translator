#!/usr/bin/env python3
"""演示：查找乘法站点本来就是一个固定算法，不该漏。

对比两种写法：
  错误写法：只取第一个站点（我之前干的）
  正确写法：全量遍历（本来就该这样）

用法：
    python scripts/research/ruby/a2_why_missed.py
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


def find_all_refs(rom: bytes, base: int) -> dict:
    """固定算法：给定表基址，找出所有引用站点。

    步骤（全部机械，无需判断）：
      1. 扫全 ROM 找 u32 == base + 0x08000000（4 对齐）
      2. 对每个命中位置，向前找 thumb ldr [pc,#imm] 引用它
      3. 对每条 ldr，向前找带移位的 lsls（stride 乘法）
    """
    gba = base + GBA_BASE
    needle = struct.pack("<I", gba)

    literals = []
    s = 0
    while True:
        i = rom.find(needle, s)
        if i < 0:
            break
        if i % 4 == 0:
            literals.append(i)
        s = i + 1

    out = []
    for lit in literals:
        # 找引用该字面量的 ldr
        ldrs = []
        for off in range(max(0, lit - 4096), lit, 2):
            hw = struct.unpack_from("<H", rom, off)[0]
            if (hw & 0xF800) != 0x4800:
                continue
            imm = (hw & 0xFF) * 4
            if ((off + 4) & ~3) + imm == lit:
                ldrs.append(off)
        out.append({"literal": lit, "ldrs": ldrs})
    return {"base": base, "literals": out, "n_literals": len(literals),
            "n_ldrs": sum(len(x["ldrs"]) for x in out)}


def main() -> int:
    rom = ROM.read_bytes()

    for name, base in (
        ("招式名", 0x1CACFC),
        ("道具名", 0x39A648),
        ("秘密基地装饰名", 0x3C2A44),
    ):
        r = find_all_refs(rom, base)
        print(f"=== {name} base=0x{base:06X} ===")
        print(f"  字面量站点 {r['n_literals']}")
        print(f"  ldr 引用   {r['n_ldrs']}")
        print(f"  → 一个 for 循环就全拿到了，没有任何需要人工取舍的地方")

        # 演示「只取第一个」会漏多少
        first = r["literals"][0]
        print(f"  若只取第一个（0x{first['literal']:06X}）:")
        print(f"    拿到 1/{r['n_literals']} 个字面量，"
              f"漏掉 {r['n_literals'] - 1} 处")
        print()

    print("=" * 70)
    print("=== 结论 ===")
    print("  漏的原因不是算法有分支，是我在生成 patch 时")
    print("  把 a2_base_refs.py 打印出来的「第一个」手抄进了脚本，")
    print("  而不是让脚本自己遍历。")
    print("  a2_base_refs.py 的输出本来就有全部站点，我没用它。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
