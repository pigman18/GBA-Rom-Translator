#!/usr/bin/env python3
"""火红「无指针」超短项到底是什么？——逐个定性。

上一脚本：中文文本区 3,125 条 ≤6 字节中文串里
  557 条有指针（555 条指针被改成指中文，99.6%）
  2,568 条「无指针」

待查：这 2,568 条是
  A. 长串内部（不是独立项，只是长文本里恰好有短片段）
  B. 变长表的元素（靠基址+偏移访问）
  C. 真正无指针的独立短项

用法：
    python scripts/research/firered/probe_short_noptr.py
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
ZH_ZONES = [(0x6D0000, 0x730000), (0x71D000, 0x720000), (0xAF5000, 0xB00000)]


def find_short(rom: bytes, max_bytes: int = 6):
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
                    out.append((i, body, j))
                    i = j + 1
                    continue
            i += 1
    return out


def ptr_sites(rom: bytes, off: int) -> list[int]:
    needle = struct.pack("<I", off + GBA_BASE)
    out, s = [], 0
    while True:
        i = rom.find(needle, s)
        if i < 0:
            break
        out.append(i)
        s = i + 1
    return out


def main() -> int:
    b = ZH.read_bytes()
    short = find_short(b)
    no_ptr = [(o, body, end) for o, body, end in short if not ptr_sites(b, o)]

    print(f"≤6 字节中文串 {len(short):,}，其中无指针 {len(no_ptr):,}\n")

    # 分类：看每个无指针串的「前一个字节」和「后一个字节」
    prev_ff = 0     # 前面是 FF（说明可能是长串被 FF 分开的片段）
    prev_other = 0
    samples = []

    for off, body, end in no_ptr[:600]:
        prev = b[off - 1] if off > 0 else 0
        if prev == 0xFF:
            prev_ff += 1
        else:
            prev_other += 1
        if len(samples) < 12:
            ctx_before = b[max(0, off - 12):off]
            ctx_after = b[end + 1:end + 13]
            samples.append((off, body, prev, ctx_before, ctx_after))

    print("=== 无指针串的「前一字节」分布（抽样 600）===")
    print(f"  前字节是 FF: {prev_ff}")
    print(f"  前字节非 FF: {prev_other}")
    print()

    print("=== 样本（看上下文判断是什么）===")
    for off, body, prev, cb, ca in samples:
        print(f"  0x{off:06X}  {len(body)//3}字  {body.hex(' ')}  前字节 0x{prev:02X}")
        print(f"    before: ...{cb.hex(' ')}")
        print(f"    after : {ca.hex(' ')}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
