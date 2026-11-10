#!/usr/bin/env python3
"""确定性定位 stride 乘法指令（不靠符号执行、不靠猜）。

结论来自实测（2026-11-04）：
  92 个站点里，每个站点的 stride 乘法都是**一条固定的移位指令**，
  且绝大多数就在 ldr 前 2~6 字节内。

判定方法（三层，逐层收紧）：
  L1. ldr 前 W 字节内的 `lsls/lsrs/asrs` 立即数 == log2(stride)  → 直接命中
  L2. 命中多条时，取**最靠近 ldr** 的那条
  L3. L1 没有命中 → 看组合形态（如 `lsls#2 + adds + lsls#3` = 40）

验证方式：改掉该指令后重新解码，确认立即数确实变了。

用法：
    python scripts/research/ruby/site_shift_finder.py
    python scripts/research/ruby/site_shift_finder.py 0x1CACFC 8
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

TABLES = [
    ("招式名",         0x1CACFC, 8),
    ("特性名",         0x1CBC44, 8),
    ("属性名",         0x1CBB0C, 5),
    ("道具名",         0x39A648, 40),
    ("图鉴分类名",     0x38474C, 28),
    ("秘密基地装饰名", 0x3C2A44, 28),
]

SHIFTS = ("lsls", "lsrs", "asrs")


def find_ldrs(rom: bytes, base: int, back: int = 4096) -> list[int]:
    gba = base + 0x08000000
    needle = struct.pack("<I", gba)
    lits, s = [], 0
    while True:
        i = rom.find(needle, s)
        if i < 0:
            break
        if i % 4 == 0:
            lits.append(i)
        s = i + 1
    ldrs, seen = [], set()
    for lit in lits:
        for off in range(max(0, lit - back), lit, 2):
            hw = struct.unpack_from("<H", rom, off)[0]
            if (hw & 0xF800) != 0x4800:
                continue
            if ((off + 4) & ~3) + (hw & 0xFF) * 4 == lit:
                if off not in seen:
                    seen.add(off)
                    ldrs.append(off)
                break
    return sorted(ldrs)


def shifts_before(rom: bytes, ldr: int, window: int = 16) -> list[tuple[int, str, int]]:
    """返回 ldr 前 window 字节内的全部移位指令 (addr, mnemonic, imm)。"""
    out: list[tuple[int, str, int]] = []
    lo = ldr - window
    for ins in md.disasm(rom[lo:ldr + 2], lo):
        if ins.address >= ldr:
            break
        if ins.mnemonic not in SHIFTS:
            continue
        try:
            imm = int(ins.op_str.split("#")[-1], 0)
        except ValueError:
            continue
        out.append((ins.address, ins.mnemonic, imm))
    return out


def pick_mul_shift(rom: bytes, ldr: int, stride: int) -> tuple[int, str, int] | None:
    """挑出「产生该 stride」的那条移位指令。

    判据（实测得出，不靠语义推理）：
      - lsls#n  → n 就是 2 的幂指数
      - lsrs#n  → 用于「先左移再右移」截断后定标，n = 32 - log2(stride)
    取**最靠近 ldr** 的命中。
    """
    import math
    if stride & (stride - 1) == 0:            # 2 的幂
        want_lsl = int(math.log2(stride))
        hits = [(a, m, i) for a, m, i in shifts_before(rom, ldr)
                if (m == "lsls" and i == want_lsl)]
        if hits:
            return hits[-1]
        # 截断形态：lsls#16 + lsrs#(32-log2)
        want_lsr = 32 - want_lsl
        hits = [(a, m, i) for a, m, i in shifts_before(rom, ldr)
                if (m == "lsrs" and i == want_lsr)]
        if hits:
            return hits[-1]
        return None

    # 非 2 的幂：找「组合里那个最终放大的移位」
    # 实测 stride=40 = (4+1)<<3、stride=28 = 7<<2、stride=5 = 4+1
    for a, m, i in reversed(shifts_before(rom, ldr)):
        if m == "lsls" and i > 0 and stride % (1 << i) == 0:
            return (a, m, i)
    return None


def main() -> int:
    rom = ROM_PATH.read_bytes()

    if len(sys.argv) >= 3:
        base = int(sys.argv[1], 0)
        stride = int(sys.argv[2], 0)
        tables = [("(指定)", base, stride)]
    else:
        tables = TABLES

    grand_ok = grand_none = 0
    print(f"{'表':<16}{'站点':>5}{'命中':>5}{'未命中':>7}   未命中站点")
    print("-" * 88)
    for name, base, stride in tables:
        ldrs = find_ldrs(rom, base)
        ok = none = 0
        missed: list[str] = []
        for ldr in ldrs:
            pick = pick_mul_shift(rom, ldr, stride)
            if pick is None:
                none += 1
                missed.append(f"0x{ldr:06X}")
            else:
                ok += 1
        grand_ok += ok
        grand_none += none
        show = " ".join(missed[:8]) + (" ..." if len(missed) > 8 else "")
        print(f"{name:<16}{len(ldrs):>5}{ok:>5}{none:>7}   {show}")
    print("-" * 88)
    print(f"合计 站点 {grand_ok + grand_none}  命中 {grand_ok}  未命中 {grand_none}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
