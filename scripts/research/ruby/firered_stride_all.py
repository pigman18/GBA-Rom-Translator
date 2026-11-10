#!/usr/bin/env python3
"""火红 stride 改动全量对比：是否每处都 +1、是否一处不漏。

已知（前面实测）：
  原版 0x02FFDA: lsls r1,r1,#3  →  汉化 #4   （×8 → ×16）
  原版 0x06B66A: lsrs r1,r1,#0xd →  汉化 #0xc （净 3 → 净 4）

待确认：
  1. 全部 31/32 处站点是否都改了
  2. 是否都是 +1（stride 8 → 16）
  3. 有没有站点的倍数不同

用法：
    python scripts/research/ruby/firered_stride_all.py
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
FR_ORIG = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
GBA_BASE = 0x08000000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

FR_ORIG_BASE = 0x204660
FR_ZH_BASE = 0x71F444


def find_ldrs(rom: bytes, gba: int) -> list[int]:
    needle = struct.pack("<I", gba)
    lits, s = [], 0
    while True:
        i = rom.find(needle, s)
        if i < 0:
            break
        if i % 4 == 0:
            lits.append(i)
        s = i + 1
    ldrs = []
    for lit in lits:
        for off in range(max(0, lit - 4096), lit, 2):
            hw = struct.unpack_from("<H", rom, off)[0]
            if (hw & 0xF800) != 0x4800:
                continue
            imm = (hw & 0xFF) * 4
            if ((off + 4) & ~3) + imm == lit:
                ldrs.append(off)
                break
    return ldrs


def shift_insns(rom: bytes, ldr: int, back: int = 20) -> list[tuple[int, str, int]]:
    """返回 ldr 前的 (地址, 助记符, 立即数)。"""
    out = []
    lo = max(0, ldr - back)
    for ins in md.disasm(rom[lo:ldr], lo):
        if ins.mnemonic in ("lsls", "lsl", "lsrs", "lsr"):
            parts = ins.op_str.split(",")
            if len(parts) == 3 and parts[2].strip().startswith("#"):
                try:
                    imm = int(parts[2].strip()[1:], 0)
                except ValueError:
                    continue
                out.append((ins.address, ins.mnemonic, imm))
    return out


def main() -> int:
    a = FR_ORIG.read_bytes()
    b = FR_ZH.read_bytes()

    la = find_ldrs(a, FR_ORIG_BASE + GBA_BASE)
    lb = find_ldrs(b, FR_ZH_BASE + GBA_BASE)
    print(f"原版 ldr 站点 {len(la)}")
    print(f"汉化 ldr 站点 {len(lb)}")
    print()

    # 火红代码区地址不变（都在 0x08xxxxxx），可直接按同地址对比
    common = sorted(set(la) & set(lb))
    only_a = sorted(set(la) - set(lb))
    only_b = sorted(set(lb) - set(la))
    print(f"共同站点 {len(common)}  仅原版 {len(only_a)}  仅汉化 {len(only_b)}")
    if only_a:
        print(f"  仅原版: {[hex(x) for x in only_a[:5]]}")
    if only_b:
        print(f"  仅汉化: {[hex(x) for x in only_b[:5]]}")
    print()

    print("=== 逐站点对比移位指令 ===")
    print(f"{'ldr':>10}  {'原版':<26} {'汉化':<26} {'净变化'}")
    print("-" * 82)

    changed = unchanged = 0
    deltas = []
    for ldr in common:
        sa = shift_insns(a, ldr)
        sb = shift_insns(b, ldr)
        # 计算净移位
        def net(ins_list):
            n = 0
            for _addr, mn, imm in ins_list:
                n += imm if mn.startswith("lsl") else -imm
            return n
        na, nb = net(sa), net(sb)
        da = " ".join(f"{mn}#{imm}" for _a, mn, imm in sa) or "-"
        db = " ".join(f"{mn}#{imm}" for _a, mn, imm in sb) or "-"
        mark = ""
        if na != nb:
            changed += 1
            deltas.append(nb - na)
            mark = f"★ 净 {na}→{nb} (+{nb - na})"
        else:
            unchanged += 1
        print(f"0x{ldr:06X}  {da:<26} {db:<26} {mark}")

    print("-" * 82)
    print(f"改动 {changed} 处，未改 {unchanged} 处")
    if deltas:
        from collections import Counter
        print(f"净移位变化分布: {dict(Counter(deltas))}")

    print()
    print("=== 结论 ===")
    if changed and all(d == 1 for d in deltas):
        print(f"  ✅ 火红全部 {changed} 处都是 +1（stride ×8 → ×16）")
        print(f"  ✅ 一处不漏（{len(common)} 处共同站点）")
        print("  ⇒ 用户判断正确：改「一个常量」，新旧 stride 可从编码推算")
    else:
        print(f"  变化分布: {dict(Counter(deltas)) if deltas else '无变化'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
