#!/usr/bin/env python3
"""A2.4 阻塞点：道具名表的「基址 0x39A648」为什么找不到字面量？

上一脚本：值为 0x0839A660（=0x39A660+0x08000000）的 4 对齐字面量 0 处。

可能：
  A. 代码用的是表基址 0x39A648（元素起点），不是名称字段 0x39A660
  B. 代码用 index×40 + 基址，基址字面量是 0x0839A648
  C. 基址根本不在代码里，靠别的表引用

本脚本对整张表的可能基址（0x39A648 ± 若干）逐一搜索。

用法：
    python scripts/research/ruby/a2_find_table_base.py
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

TABLE = 0x39A648      # 元素起点（entry_size=40 的第一项）
NAME_OFF = 0x18


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

    print("=== 在 0x39A648 ± 0x40 范围找被引用的基址 ===")
    hits = []
    for delta in range(-0x40, 0x41):
        cand = TABLE + delta
        pat = struct.pack("<I", cand + GBA_BASE)
        sites = []
        s = 0
        while True:
            i = rom.find(pat, s)
            if i < 0:
                break
            if i % 4 == 0:
                sites.append(i)
            s = i + 1
        if sites:
            ldr_n = sum(1 for x in sites if ldr_refs(rom, x))
            hits.append((cand, delta, len(sites), ldr_n, sites))

    for cand, delta, n, ldr_n, sites in hits:
        mark = "  ← 名称字段起点" if delta == NAME_OFF else ""
        print(f"  0x{cand:06X} (Δ{delta:+3d})  字面量 {n} 处，ldr 确认 {ldr_n}"
              + mark)
        for s in sites[:4]:
            ldrs = ldr_refs(rom, s)
            print(f"     0x{s:06X}" + (f" ← ldr 0x{ldrs[0]:X}" if ldrs else ""))
    print()

    if not hits:
        print("❌ 整个 0x39A648 附近都没有被引用的基址")
        print()
        print("=== 换个思路：找指向这个区域内的所有指针 ===")
        cnt = 0
        for off in range(0, len(rom) - 4):
            v = struct.unpack_from("<I", rom, off)[0]
            if GBA_BASE <= v < 0x0A000000:
                t = v - GBA_BASE
                if 0x39A000 <= t < 0x39E000:
                    cnt += 1
                    if cnt <= 10:
                        print(f"    0x{off:06X} → 0x{t:06X}")
        print(f"  指向 0x39A000-0x39E000 的指针共 {cnt:,} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
