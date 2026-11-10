#!/usr/bin/env python3
"""火红指针数组怎么被代码访问？——查间接引用链。

上一支脚本发现：0x726124 / 0x71BFB4 等指针数组，
没有任何代码段字面量直接引用它们的基址。但游戏显然能读到。

可能：
  A. 有一个「指针的指针」——代码读某个字面量，那个字面量指向含数组地址的表
  B. 代码用「基址 + 偏移」计算（数组本身在更大的结构里）
  C. 数组基址以裸偏移或非 4 对齐方式存着

本脚本查 A：找「其值等于数组 GBA 地址」的任何位置（含非对齐）。

用法：
    python scripts/research/firered/probe_array_refs.py
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
ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"

GBA_BASE = 0x08000000
ARRAYS = [0x726124, 0x71BFB4, 0x71C404, 0x71F234, 0x711940, 0x7B85B4]


def find_refs(rom: bytes, target_gba: int) -> list[int]:
    """找所有指向该地址的位置（不要求 4 字节对齐）。"""
    needle = struct.pack("<I", target_gba)
    out, s = [], 0
    while True:
        i = rom.find(needle, s)
        if i < 0:
            break
        out.append(i)
        s = i + 1
    return out


def main() -> int:
    rom = ZH.read_bytes()
    print(f"zh {len(rom):,} B\n")

    for arr in ARRAYS:
        refs = find_refs(rom, arr + GBA_BASE)
        print(f"=== 数组 0x{arr:06X} ===")
        print(f"  指向它的位置: {len(refs)} 处")
        for r in refs[:8]:
            aligned = "4对齐" if r % 4 == 0 else "非对齐"
            ctx = rom[max(0, r - 8):r + 12].hex(" ")
            print(f"    0x{r:06X} ({aligned})  ctx: {ctx}")
        if refs:
            # 如果是 4 对齐且在代码段，看能否找到 ldr
            for r in refs[:4]:
                if r % 4 or r > 0x200000:
                    continue
                for off in range(max(0, r - 2048), r, 2):
                    hw = struct.unpack_from("<H", rom, off)[0]
                    if (hw & 0xF800) != 0x4800:
                        continue
                    imm = (hw & 0xFF) * 4
                    if ((off + 4) & ~3) + imm == r:
                        print(f"      ← ldr @ 0x{off:X}")
                        break
        print()

    # 换个思路：火红的「指针数组」是不是嵌在某个更大的表里？
    print("=== 数组前后 32 字节（看是否嵌在大结构里）===")
    for arr in ARRAYS[:3]:
        lo = max(0, arr - 32)
        print(f"  0x{arr:06X}:")
        print(f"    -32..: {rom[lo:arr].hex(' ')}")
        print(f"    +00..: {rom[arr:arr + 32].hex(' ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
