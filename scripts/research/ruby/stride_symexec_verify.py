#!/usr/bin/env python3
"""用符号执行求出每个站点的 stride —— 确定性结果，不猜。

对每张表的全部 ldr 站点：
  1. 扫字面量 + 找 ldr（确定集合）
  2. 符号执行求 `base + index` 的系数 K
  3. 判定：K == 旧 stride → 该站点要改；否则不改（明确理由）

输出：每个站点一行，写明 K 值或失败原因。

用法：
    python scripts/research/ruby/stride_symexec_verify.py
"""
from __future__ import annotations

import struct
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
GBA_BASE = 0x08000000
LDR_PC_MASK = 0xF800
LDR_PC_OP = 0x4800

TABLES = [
    ("招式名",         0x1CACFC, 8,  16),
    ("特性名",         0x1CBC44, 8,  16),
    ("属性名",         0x1CBB0C, 5,  10),
    ("道具名",         0x39A648, 40, 80),
    ("图鉴分类名",     0x38474C, 28, 56),
    ("秘密基地装饰名", 0x3C2A44, 28, 56),
]


def find_ldrs(rom: bytes, base: int, back: int = 4096) -> list[int]:
    gba = base + GBA_BASE
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
            if (hw & LDR_PC_MASK) != LDR_PC_OP:
                continue
            imm = (hw & 0xFF) * 4
            if ((off + 4) & ~3) + imm == lit:
                if off not in seen:
                    seen.add(off)
                    ldrs.append(off)
                break
    return sorted(ldrs)


def main() -> int:
    from meowth.thumb_symexec import solve_site

    rom = ROM.read_bytes()

    grand_total = grand_solved = grand_match = 0
    all_ok = True

    for name, base, old_s, new_s in TABLES:
        ldrs = find_ldrs(rom, base)
        print(f"\n{'=' * 78}")
        print(f"=== {name}  base=0x{base:06X}  stride {old_s}→{new_s}  "
              f"ldr 站点 {len(ldrs)} ===")
        print("=" * 78)

        solved = 0
        match = 0
        others = Counter()
        fails = []

        for ldr in ldrs:
            # 该 ldr 加载的是表基址 → base_reg
            hw = struct.unpack_from("<H", rom, ldr)[0]
            r = solve_site(rom, ldr)
            if r.stride is None:
                fails.append((ldr, r.reason))
                continue
            solved += 1
            if r.stride == old_s:
                match += 1
                others[f"K={r.stride}"] += 1
            else:
                others[f"K={r.stride}(非本表)"] += 1

        grand_total += len(ldrs)
        grand_solved += solved
        grand_match += match
        if solved != len(ldrs) or match != len(ldrs):
            all_ok = False

        print(f"  求解成功 {solved}/{len(ldrs)}   K==旧stride {match}/{len(ldrs)}")
        print(f"  K 分布: {dict(others)}")
        if fails:
            print(f"  求解失败 {len(fails)}:")
            for ldr, why in fails[:6]:
                print(f"    0x{ldr:06X}  {why}")

    print(f"\n{'=' * 78}")
    print("=== 总计 ===")
    print(f"  ldr 站点      {grand_total}")
    print(f"  求解成功      {grand_solved} ({grand_solved / grand_total:.0%})")
    print(f"  K==旧stride   {grand_match} ({grand_match / grand_total:.0%})")
    print()
    if all_ok:
        print("✅ 全部站点：K 已确定且等于旧 stride，可精确改写")
        return 0
    print("⚠️ 存在求解失败或 K 不等于旧 stride 的站点（见上）")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
