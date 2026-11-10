#!/usr/bin/env python3
"""texts_57: 溯源 0x3B3E64 指针表 —— 谁在用它、是干什么的。

Chief 要求：
  1. 这张表有没有代码引用（搜指向 0x083B3E64 的字面量）
  2. 若被引用，看那个函数干什么（读反汇编，别猜）
  3. 22 项这个数量像什么

同时查 0x3B2670（第 0 项解码为空）到底是什么。

用法: python scripts/research/ruby/texts_57_ptrtable_purpose.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
SYM = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "symbols" / "pokeruby_jp.sym"
BASE = 0x08000000

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import decode_pcs  # noqa: E402

TABLE = 0x3B3E64


def main() -> int:
    rom = ROM_PATH.read_bytes()
    n = len(rom)

    print("=" * 112)
    print("1) 搜指向 0x083B3E64 的字面量（对齐 + 非对齐）")
    print("=" * 112)
    target = BASE + TABLE
    aligned, unaligned = [], []
    for o in range(0, n - 4, 4):
        if struct.unpack_from("<I", rom, o)[0] == target:
            aligned.append(o)
    for o in range(1, n - 4):
        if (o & 3) == 0:
            continue
        if rom[o + 3] != 0x08:
            continue
        if struct.unpack_from("<I", rom, o)[0] == target:
            unaligned.append(o)
    print(f"  对齐字面量: {[hex(x) for x in aligned] or '无'}")
    print(f"  非对齐字面量: {[hex(x) for x in unaligned] or '无'}")

    # 也搜「表地址附近」的引用（有的代码用 base+4*n 索引）
    near = []
    for o in range(0, n - 4, 4):
        v = struct.unpack_from("<I", rom, o)[0]
        if BASE + TABLE - 0x40 <= v <= BASE + TABLE + 0x40:
            near.append((o, v))
    print(f"  表地址 ±0x40 内的字面量: {[(hex(a), hex(v)) for a, v in near] or '无'}")

    print()
    print("=" * 112)
    print("2) 符号表里 0x3B3E64 附近有什么符号")
    print("=" * 112)
    if SYM.exists():
        hits = []
        for line in SYM.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split()
            if not parts:
                continue
            try:
                addr = int(parts[0], 16)
            except ValueError:
                continue
            if 0x3B3C00 <= addr <= 0x3B4200:
                hits.append((addr, line))
        if hits:
            for addr, line in sorted(hits)[:20]:
                print(f"  0x{addr:06X}  {line[:100]}")
        else:
            print("  该区段无符号")
        # 找最接近 0x3B3E64 之前的符号
        prev = None
        for line in SYM.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split()
            if not parts:
                continue
            try:
                addr = int(parts[0], 16)
            except ValueError:
                continue
            if 0x08000000 <= addr <= BASE + TABLE:
                prev = (addr, line)
        if prev:
            print(f"\n  最接近 0x3B3E64 之前的符号: 0x{prev[0]:06X} {prev[1][:100]}")

    print()
    print("=" * 112)
    print("3) 0x3B2670 到底是什么（第 0 项解码为空）")
    print("=" * 112)
    for probe in (0x3B2670, 0x3B2660, 0x3B2680):
        seg = rom[probe:probe + 32]
        print(f"  0x{probe:06X}: {seg.hex(' ')}")
        print(f"           解码: {decode_pcs(seg)!r}")

    print()
    print("=" * 112)
    print("4) 22 项这个数量的语义推测依据")
    print("=" * 112)
    print("  已知定长表规模：性格 25 / 华丽大赛属性 4 / 属性 18 / 招式 354 / 特性 77")
    print("  本表 22 项（有效指针 18 项，其后 4 项指向区间外或解码为空）")
    print()
    print("  逐项内容：")
    for k in range(18):
        v = struct.unpack_from("<I", rom, TABLE + k * 4)[0]
        t = v - BASE
        s = ""
        for i in range(t, min(n, t + 64)):
            if rom[i] == 0xFF:
                s = decode_pcs(rom[t:i + 1])
                break
        print(f"    [{k:>2}] {s!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
