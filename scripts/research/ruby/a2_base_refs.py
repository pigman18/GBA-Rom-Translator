#!/usr/bin/env python3
"""查：招式名/特性名/属性名/装饰名 的基址到底被什么引用？

a2_stride_swap 报「指向文件偏移 0x1CACFC 的字面量 0 处」，
而 a1 系列脚本曾说 招式名 基址 0x1CACFC 被引用 43 次。

矛盾原因：a1 扫的是「含非对齐」，本脚本用 find_ldr（只认 ldr 引用）。

必须分清：
  字面量站点（u32 == base + 0x08000000）有几处、对齐与否
  其中被 ldr [pc] 引用的有几处

用法：
    python scripts/research/ruby/a2_base_refs.py
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
GBA_BASE = 0x08000000

BASES = [
    ("招式名",         0x1CACFC),
    ("特性名",         0x1CBC44),
    ("属性名",         0x1CBB0C),
    ("秘密基地装饰名", 0x3C2A44),
    ("道具名",         0x39A648),
    ("图鉴分类名",     0x38474C),
]


def all_sites(rom: bytes, gba: int) -> tuple[list[int], list[int]]:
    needle = struct.pack("<I", gba)
    aligned, unaligned = [], []
    s = 0
    while True:
        i = rom.find(needle, s)
        if i < 0:
            break
        (aligned if i % 4 == 0 else unaligned).append(i)
        s = i + 1
    return aligned, unaligned


def ldr_refs(rom: bytes, lit: int, back: int = 4096) -> list[int]:
    out = []
    for off in range(max(0, lit - back), lit, 2):
        hw = struct.unpack_from("<H", rom, off)[0]
        if (hw & 0xF800) != 0x4800:
            continue
        imm = (hw & 0xFF) * 4
        if ((off + 4) & ~3) + imm == lit:
            out.append(off)
    return out


def main() -> int:
    rom = ROM_PATH.read_bytes()

    print(f"{'表':<16} {'基址':>10} {'对齐字面量':>10} {'ldr确认':>8} {'非对齐':>8}")
    print("-" * 60)
    for name, base in BASES:
        gba = base + GBA_BASE
        al, un = all_sites(rom, gba)
        ldr_n = sum(1 for s in al if ldr_refs(rom, s))
        print(f"{name:<16} 0x{base:06X} {len(al):>10} {ldr_n:>8} {len(un):>8}")

    print()
    print("=== 详细：每张表的对齐字面量位置 ===")
    for name, base in BASES:
        gba = base + GBA_BASE
        al, _ = all_sites(rom, gba)
        if not al:
            print(f"  {name}: 无对齐字面量")
            continue
        print(f"  {name} (0x{gba:08X}) {len(al)} 处:")
        for s in al[:6]:
            ldrs = ldr_refs(rom, s)
            print(f"    站点 0x{s:06X}" +
                  (f"  ← ldr 0x{ldrs[0]:X}" if ldrs else "  (无 ldr)"))

    # 关键：检查「前一字节偏移」的基址（之前发现表基址可能差 8 字节）
    print()
    print("=== 检查 ±16 范围内的邻近基址 ===")
    for name, base in BASES:
        hits = []
        for d in range(-16, 17):
            cand = base + d
            al, _ = all_sites(rom, cand + GBA_BASE)
            if al:
                ldr_n = sum(1 for s in al if ldr_refs(rom, s))
                hits.append((cand, d, len(al), ldr_n))
        if hits:
            print(f"  {name} (配置 0x{base:06X}):")
            for cand, d, n, ln in hits:
                print(f"    0x{cand:06X} (Δ{d:+3d})  字面量 {n}  ldr {ln}"
                      + ("  ← 就是配置值" if d == 0 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
