#!/usr/bin/env python3
"""正确定位 ldr 所在「基本块」，并判断 index 从哪来。

现状问题（实测）：
  0x09C6C4（特性名）所在的块，前面是 `b 0x9C6F0`（0x09C604），
  所以「从函数入口直落」永远到不了。以前算出的 K=8 是抖出来的巧合。

思路（正确做法）：
  1. 从 ldr 反向走，找到「块头」——前一条是 b/bcond/bl/bx/pop-pc 的位置
  2. 在块内正向走，符号执行只在这个块内
  3. index 的来源必然是块外的输入（bl 返回值 / 内存读 / 函数参数）

这里先只做「定位块 + 打印」，用真实数据说话，不猜。

用法：
    python scripts/research/ruby/block_probe.py 0x09C6C4
    python scripts/research/ruby/block_probe.py 0x0A5432
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
sys.path.insert(0, str(ROOT / "src"))

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)


def is_block_end(mn: str, ops: str) -> bool:
    if mn in ("bx", "bxns", "blx"):
        return True
    if mn == "pop" and "pc" in ops:
        return True
    if mn == "b":
        return True
    return False


def block_head(rom: bytes, ldr: int, back: int = 0x120) -> int:
    """从 ldr 反向找块头：上一条是 branch/return 的那条之后。"""
    lo = max(0, ldr - back)
    pc = ldr - 2
    while pc >= lo:
        ins = next(md.disasm(rom[pc:pc + 2], pc), None)
        if ins and is_block_end(ins.mnemonic, ins.op_str):
            return pc + 2
        pc -= 2
    return lo


def main() -> int:
    rom = ROM_PATH.read_bytes()
    ldr = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x09C6C4

    head = block_head(rom, ldr)
    print(f"=== ldr 0x{ldr:06X}  所在基本块头 0x{head:06X} ===")
    print()
    print("--- 块内容（从此走到 ldr 之后一段）---")
    for ins in md.disasm(rom[head:ldr + 40], head):
        m = "  ★ ldr" if ins.address == ldr else ""
        print(f"  0x{ins.address:06X}: {ins.bytes.hex(' '):<9} "
              f"{ins.mnemonic:<7} {ins.op_str}{m}")

    print()
    print("--- 块头前 6 条（看是谁跳到这块的）---")
    for ins in md.disasm(rom[max(0, head - 24):head], max(0, head - 24)):
        print(f"  0x{ins.address:06X}: {ins.bytes.hex(' '):<9} "
              f"{ins.mnemonic:<7} {ins.op_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
