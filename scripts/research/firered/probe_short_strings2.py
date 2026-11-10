#!/usr/bin/env python3
"""火红超短项：只在真实中文文本区内统计，排除代码段误报。

上一脚本的问题：
  扫全文找「F7 开头 + FF 结尾 + ≤6 字节」，大量命中代码段里的
  `f7 e7 fc` 这类指令字节组合，导致「93.6% 无指针」的假象。

修正：只扫已知中文文本区
  0x6D0000..0x730000  主文本区
  0x71D000..0x720000  文本区 2
  0xAF5000..0xB00000  文本区 3

用法：
    python scripts/research/firered/probe_short_strings2.py
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
ZH_ZONES = [(0x6D0000, 0x730000), (0x71D000, 0x720000), (0xAF5000, 0xB00000)]


def find_short_in_zones(rom: bytes, max_bytes: int = 6):
    """只在中文文本区内找 ≤max_bytes 的中文串。"""
    out = []
    for lo, hi in ZH_ZONES:
        i = lo
        while i < hi - 3:
            if rom[i] != 0xF7:
                i += 1
                continue
            j = i
            while j < hi and rom[j] != 0xFF and (j - i) < max_bytes:
                j += 1
            if j < hi and rom[j] == 0xFF:
                body = rom[i:j]
                if len(body) >= 3 and len(body) % 3 == 0:
                    out.append((i, body))
                    i = j + 1
                    continue
            i += 1
    return out


def ptr_sites(rom: bytes, target_off: int) -> list[int]:
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

    short = find_short_in_zones(b, max_bytes=6)
    print(f"中文文本区内 ≤6 字节的中文串: {len(short):,} 个\n")

    has_ptr = no_ptr = 0
    changed = unchanged = 0
    samples = []
    for off, body in short:
        refs = ptr_sites(b, off)
        if not refs:
            no_ptr += 1
            continue
        has_ptr += 1
        # 看首个指针位置的旧值是否被改
        r0 = refs[0]
        if r0 + 4 <= len(a):
            old = struct.unpack_from("<I", a, r0)[0]
            new = struct.unpack_from("<I", b, r0)[0]
            if old != new:
                changed += 1
            else:
                unchanged += 1
        if len(samples) < 8:
            samples.append((off, body, refs, old if r0 + 4 <= len(a) else 0,
                            new if r0 + 4 <= len(b) else 0))

    total = has_ptr + no_ptr
    print("=== ≤6 字节中文串的指针情况（仅在文本区）===")
    print(f"  有指针: {has_ptr:,} ({has_ptr/total:.1%})")
    print(f"  无指针: {no_ptr:,} ({no_ptr/total:.1%})")
    print(f"  其中指针被改成指中文: {changed:,}")
    print(f"  指针未改（可能仍指原版）: {unchanged:,}")
    print()

    print("=== 样本（看指针怎么被改的）===")
    for off, body, refs, old, new in samples:
        n = len(body) // 3
        code_refs = [r for r in refs if r < CODE_END]
        print(f"  0x{off:06X}  {n} 字  {body.hex(' ')}   指针 {len(refs)} 处（代码段 {len(code_refs)}）")
        print(f"    首个 @0x{refs[0]:X}: 原版 0x{old:08X} → 汉化 0x{new:08X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
