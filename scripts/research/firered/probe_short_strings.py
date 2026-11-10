#!/usr/bin/env python3
"""火红超短项（是/否 等）怎么处理？——逐个实测。

用户判断：火红超短项也是「写死地址重定向」，不是替换表。需要核实。

已知（FIRERED_FULL_LOGIC 2.5）：508 条 ≤6 字节中文段，502 条有指针（98.8%）。
但「有指针」不等于「指针被改」。本脚本验证：
  1. 火红汉化版里 ≤6 字节的中文串，其指针在 origin vs 汉化 是否被改
  2. 「はい / いいえ」（是/否）这类选项具体在哪
  3. 若原件无指针，火红怎么处理

用法：
    python scripts/research/firered/probe_short_strings.py
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
CODE_END = 0x200000


def find_zh_short_strings(rom: bytes, max_bytes: int = 6, limit: int = 4000):
    """找「以 FF 结尾、长度 ≤max_bytes、含 ≥1 个 F7 中文」的串。"""
    out = []
    n = len(rom)
    i = 0
    while i < n - 3 and len(out) < limit:
        # 必须以 F7 开头（中文串起点）
        if rom[i] != 0xF7:
            i += 1
            continue
        j = i
        # 走到 FF
        while j < n and rom[j] != 0xFF and (j - i) < max_bytes:
            j += 1
        if j < n and rom[j] == 0xFF:
            body = rom[i:j]
            # body 应该是 3 的倍数（F7 hi lo）
            if len(body) >= 3 and len(body) % 3 == 0:
                out.append((i, body))
        i += 1
    return out


def ptr_count(rom: bytes, target_off: int) -> list[int]:
    """找指向该地址的 u32（含非对齐）。"""
    needle = struct.pack("<I", target_off + GBA_BASE)
    out, s = [], 0
    while True:
        i = rom.find(needle, s)
        if i < 0:
            break
        out.append(i)
        s = i + 1
    return out


def main() -> int:
    a = ORIG.read_bytes()
    b = ZH.read_bytes()

    short = find_zh_short_strings(b, max_bytes=6)
    print(f"汉化版里 ≤6 字节的中文串: {len(short):,} 个\n")

    has_ptr = 0
    no_ptr = 0
    sample_hit = []
    sample_miss = []

    for off, body in short:
        refs = ptr_count(b, off)
        if refs:
            has_ptr += 1
            if len(sample_hit) < 6:
                sample_hit.append((off, body, refs))
        else:
            no_ptr += 1
            if len(sample_miss) < 6:
                sample_miss.append((off, body))

    total = has_ptr + no_ptr
    print("=== 超短项是否有指针指向 ===")
    print(f"  有指针: {has_ptr:,} ({has_ptr/total:.1%})")
    print(f"  无指针: {no_ptr:,} ({no_ptr/total:.1%})")
    print()

    print("=== 有指针的样本（看指针来源是不是代码/脚本）===")
    for off, body, refs in sample_hit:
        nchar = len(body) // 3
        code_refs = [r for r in refs if r < CODE_END]
        print(f"  0x{off:06X}  {nchar} 字  {body.hex(' ')}")
        print(f"    指针 {len(refs)} 处，代码段 {len(code_refs)} 处"
              + (f": {', '.join(f'0x{r:X}' for r in refs[:4])}"))
        # 该指针位置在原版是什么
        r0 = refs[0]
        old = struct.unpack_from("<I", a, r0)[0]
        new = struct.unpack_from("<I", b, r0)[0]
        print(f"    首个指针位置 0x{r0:X}: 原版 0x{old:08X} → 汉化 0x{new:08X}"
              + ("  ← 已改指中文" if old != new else "  ← 未改"))
        print()

    print("=== 无指针的样本 ===")
    for off, body in sample_miss:
        print(f"  0x{off:06X}  {len(body)//3} 字  {body.hex(' ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
