#!/usr/bin/env python3
"""坐实：火红原版本来就有指针数组，汉化只是把指针值改成指向中文串。

上一支脚本关键发现：
  0x71C404 之前 32 字节 = 06 43 20 08 0c 43 20 08 ...  ← 指向 0x082043xx 的指针
  0x71C404 本身       = fc af 71 08 08 b0 71 08 ...    ← 指向 0x0871AFxx 的指针

前者是原版就有的指针数组（指日文），后者是汉化新增的。

本脚本验证：
  1. 原版同位置 0x71C404 是什么（是否也是指针数组）
  2. 若原版也是指针数组 → 火红是「原地改指针值」，不是「新增数组」
  3. 统计全 ROM「原版是指针数组、汉化还是指针数组」的比例

用法：
    python scripts/research/firered/probe_orig_arrays.py
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
ORIG = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"

GBA_BASE = 0x08000000
PROBES = [0x726124, 0x71BFB4, 0x71C404, 0x71F234, 0x711940]


def as_ptr(rom: bytes, off: int) -> int | None:
    if off + 4 > len(rom):
        return None
    v = struct.unpack_from("<I", rom, off)[0]
    return v - GBA_BASE if GBA_BASE <= v < 0x0A000000 else None


def ptr_run(rom: bytes, off: int, n: int) -> int:
    """从 off 起连续 n 个位置里有多少是合法 GBA 指针。"""
    cnt = 0
    for i in range(n):
        if as_ptr(rom, off + i * 4) is not None:
            cnt += 1
    return cnt


def main() -> int:
    a = ORIG.read_bytes()
    b = ZH.read_bytes()
    print(f"origin / zh 各 {len(a):,} B\n")

    for off in PROBES:
        print(f"=== 0x{off:06X} ===")
        for tag, rom in (("原版", a), ("汉化", b)):
            run = ptr_run(rom, off, 16)
            first = as_ptr(rom, off)
            print(f"  {tag}: 前 16 项中 {run}/16 是 GBA 指针"
                  + (f"，首项 → 0x{first:06X}" if first is not None else ""))
        # 原版该地址的第一个指针指向哪
        op = as_ptr(a, off)
        if op is not None:
            seg = a[op:op + 16]
            print(f"  原版首指针指向的日文串: {seg.hex(' ')}")
        print()

    # 全局统计：汉化版里「指针数组」有多少，其中原版同位置也是指针数组的有多少
    print("=== 全局：汉化新增指针数组 vs 原版已有 ===")
    zh_arrays = 0
    pre_exist = 0
    for off in range(0, len(b) - 4 * 16, 4):
        if ptr_run(b, off, 16) == 16:
            # 确认前一个位置不是（避免重复计数同一数组）
            if ptr_run(b, off - 4, 16) != 16:
                zh_arrays += 1
                if ptr_run(a, off, 16) >= 8:
                    pre_exist += 1
    print(f"  汉化版 ≥16 元素指针数组: {zh_arrays:,} 个")
    print(f"  其中原版同位置也是指针数组: {pre_exist:,} ({pre_exist/max(zh_arrays,1):.1%})")
    print()
    print("  ⇒ 高比例 = 火红「原地改指针值」；低比例 = 火红「新增数组」")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
