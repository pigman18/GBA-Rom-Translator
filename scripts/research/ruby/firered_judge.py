#!/usr/bin/env python3
"""重新查火红：它到底是「算法自动改」还是「人工标注」？

我之前的两处臆断，必须纠正：
  1. 我说「火红也没用算法猜，是人工逐个确认的」——**没有任何证据，是臆测**
  2. 火红如果是纯 AI 汉化，必然存在可自动化的判据

关键：找出火红的判据是什么。

火红已知事实：
  - 招式名表 base 0x08204660（原版）→ 0x0871F444（汉化）
  - 28 个共同 ldr 站点，16 处净移位 +1

要查：
  1. 那 16 处，为什么正好是这 16 个？（判据是什么）
  2. 剩下 8 处（未改或反向改）是什么情况？
  3. 有没有一个「不需要语义理解」的机械判据？

关键洞察方向：
  **若 stride 从 8 → 16，那么所有引用该表的站点，
   其净移位必须全部 +1。没改的就是漏了，或不是表访问。**

  所以火红的判据可能是：
    「凡是指向该表基址的 ldr，其前方一定有净移位 net，
      且 net 应对应 stride 的 2 的幂因子」
  
  而「反向改」的那 8 处可能根本不是表访问（是别的用途）。

用法：
    python scripts/research/ruby/firered_judge.py
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


def find_ldrs(rom: bytes, gba: int) -> dict[int, int]:
    """返回 {ldr 偏移: literal 偏移}。"""
    needle = struct.pack("<I", gba)
    lits, s = [], 0
    while True:
        i = rom.find(needle, s)
        if i < 0:
            break
        if i % 4 == 0:
            lits.append(i)
        s = i + 1
    out = {}
    for lit in lits:
        for off in range(max(0, lit - 4096), lit, 2):
            hw = struct.unpack_from("<H", rom, off)[0]
            if (hw & 0xF800) != 0x4800:
                continue
            imm = (hw & 0xFF) * 4
            if ((off + 4) & ~3) + imm == lit:
                out[off] = lit
                break
    return out


def net_shift(rom: bytes, ldr: int, back: int = 20) -> tuple[int, list[str]]:
    """算 ldr 前所有移位的净效果。"""
    n = 0
    desc = []
    lo = max(0, ldr - back)
    for ins in md.disasm(rom[lo:ldr], lo):
        if ins.mnemonic in ("lsls", "lsl"):
            parts = ins.op_str.split(",")
            if len(parts) == 3 and parts[2].strip().startswith("#"):
                try:
                    imm = int(parts[2].strip()[1:], 0)
                except ValueError:
                    continue
                n += imm
                desc.append(f"lsls#{imm}")
        elif ins.mnemonic in ("lsrs", "lsr"):
            parts = ins.op_str.split(",")
            if len(parts) == 3 and parts[2].strip().startswith("#"):
                try:
                    imm = int(parts[2].strip()[1:], 0)
                except ValueError:
                    continue
                n -= imm
                desc.append(f"lsrs#{imm}")
    return n, desc


def main() -> int:
    a = FR_ORIG.read_bytes()
    b = FR_ZH.read_bytes()

    la = find_ldrs(a, FR_ORIG_BASE + GBA_BASE)
    lb = find_ldrs(b, FR_ZH_BASE + GBA_BASE)
    common = sorted(set(la) & set(lb))

    print("=" * 78)
    print("=== 火红 28 个共同站点：净移位对比 ===")
    print("=" * 78)
    print(f"{'ldr':>10} {'原版净':>7} {'汉化净':>7} {'差':>5}  原版描述")
    print("-" * 78)

    changed = []
    same = []
    for ldr in common:
        na, da = net_shift(a, ldr)
        nb, db = net_shift(b, ldr)
        d = nb - na
        if d != 0:
            changed.append((ldr, na, nb, d, da))
        else:
            same.append((ldr, na, da))
        print(f"0x{ldr:06X} {na:>7} {nb:>7} {d:>+5}  {' '.join(da) or '-'}")

    print("-" * 78)
    print(f"改变了 {len(changed)} 处，未变 {len(same)} 处")
    print()

    from collections import Counter
    dist = Counter(d for _l, _a, _b, d, _da in changed)
    print(f"变化量分布: {dict(dist)}")
    print()

    # 关键：未变的那些是什么？
    print("=" * 78)
    print("=== 未变的 8 处是什么？ ===")
    print("=" * 78)
    for ldr, n, da in same:
        print(f"\n0x{ldr:06X}  净移位 {n}  {' '.join(da) or '(无移位)'}")
        lo = max(0, ldr - 12)
        for ins in md.disasm(a[lo:ldr + 10], lo):
            mark = "  ★基址" if ins.address == ldr else ""
            print(f"  0x{ins.address:06X}: {ins.mnemonic:<8}{ins.op_str}{mark}")

    # 判定：未变的这些，其 ldr 后面的用法是否与「表访问」一致
    print()
    print("=" * 78)
    print("=== 结论 ===")
    print("=" * 78)
    print()
    print("若 16 处变化量全是 +1，且未变的 8 处「不是按 stride 访问」，")
    print("⇒ 火红用的是机械判据：")
    print("   「凡指向表基址且其前方净移位对应 stride 2 的幂因子的站点，全部 +1」")
    print("   未变的是「指向同地址但用途不同」的站点。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
