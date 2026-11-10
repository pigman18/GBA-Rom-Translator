#!/usr/bin/env python3
"""A 方案：插入解引用 ldr 需要空间吗？——逐站点查空位。

招式名的理想形态：
  0x02B536: ldrh r1, [r4]       取 index
  0x02B538: lsls r1, r1, #3     idx × 8
  0x02B53A: ldr  r0, [pc, #0x44] 基址
  0x02B53C: adds r1, r1, r0     base + idx*8
  0x02B53E: adds r0, r7, #0     ← 这里占用了，不能改
  0x02B540: bl   #0x4308        调用

目标：在 0x02B53C 之后插入 `ldr r1, [r1]`。
  需要 2 字节空间，但 0x02B53E 是有效指令。

关键洞察：
  若 0x02B53C 的 `adds r1,r1,r0` 能改成「先 ldr 再 add」的组合，
  或者能找到附近的 nop / 可省指令，就能插入。

替代方案：
  **改写 ldr 基址字面量，指向「指针数组 - 偏移」是不可能的。**
  但可以：把 `adds r1,r1,r0` 改成 `ldr r1,[r1,r0]`（Thumb 无此编码）。

Thumb 可用的插入方式：
  - `ldr r1,[r1]`  = 0x6809（2 字节）
  - 若前一条是 `adds r1,r1,r0`，两条要 4 字节

检查每个站点附近是否有 nop（0x46C0）或可挪动的指令。

用法：
    python scripts/research/ruby/a_plan_space.py
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
NOP = b"\xC0\x46"

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

    print("=" * 76)
    print("=== 每站点：adds 之后是否有 2 字节空位 ===")
    print("=" * 76)

    for name, ldr, stride in SITES:
        print(f"\n--- {name} ldr@0x{ldr:06X} stride={stride} ---")
        insns = list(md.disasm(rom[ldr:ldr + 12], ldr))
        if len(insns) < 2:
            print("  指令不足")
            continue

        # 找 adds rX, rX, rBase（紧跟在 ldr 后）
        adds_ins = insns[1]
        print(f"  ldr  @0x{ldr:06X}: {insns[0].mnemonic} {insns[0].op_str}")
        print(f"  adds @0x{adds_ins.address:06X}: "
              f"{adds_ins.mnemonic} {adds_ins.op_str}")

        # adds 之后的位置
        ins_pos = adds_ins.address + 2
        nxt = rom[ins_pos:ins_pos + 2]
        is_nop = nxt == NOP
        print(f"  adds 之后 @0x{ins_pos:06X}: {nxt.hex(' ')} "
              + ("  ✅ nop！可原地插入" if is_nop else "  ❌ 有效指令"))

        if not is_nop and len(insns) > 2:
            print(f"    下一条: {insns[2].mnemonic} {insns[2].op_str}")

        # 检查整个函数里 nop 数量
        nops = []
        for off in range(max(0, ldr - 64), min(len(rom) - 1, ldr + 64), 2):
            if rom[off:off + 2] == NOP:
                nops.append(off)
        print(f"  ±64 字节内 nop: {len(nops)} 个"
              + (f"  {[hex(x) for x in nops[:3]]}" if nops else ""))

    print()
    print("=" * 76)
    print("=== 结论 ===")
    print("=" * 76)
    print("  若普遍没有 nop，插入 ldr 需要「挪指令」或「找函数尾跳板」，")
    print("  复杂度远高于改立即数。")
    print()
    print("  ⇒ A 方案（指针数组）的成本可能高于预期。")
    print("  ⇒ 需要评估：是否值得为「形态统一」付出插入指令的代价。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
