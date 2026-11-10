#!/usr/bin/env python3
"""火红「是 / 否」选项的处理方式——精确定位。

已知：中文文本区 3,125 条 ≤6 字节中文串，557 条有指针，其中 555 条指针被改成指中文。
其余 2,568 条是长串被 FD 分段指令切开的片段，不是独立项。

本脚本专门找「是/否」这类选项串，验证它们的指针来源。
火红字符集里「是=はい」「否=いいえ」，中文「是」「否」各 1 字。

做法：找 1 字中文串（3 字节 + FF = 4 字节），看它们的指针情况。

用法：
    python scripts/research/firered/probe_yes_no.py
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


def find_one_char(rom: bytes):
    """找「F7 hi lo FF」= 恰好 1 个汉字 + 结束的串。"""
    out = []
    for lo, hi in ZH_ZONES:
        i = lo
        while i < hi - 4:
            if rom[i:i + 1] == b"\xF7" and rom[i + 3:i + 4] == b"\xFF":
                # 且前面不是 F7（避免取到长串中间）
                if i == lo or rom[i - 1] != 0xF7:
                    out.append((i, rom[i:i + 3]))
                    i += 4
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
    a = ORIG.read_bytes()
    b = ZH.read_bytes()

    ones = find_one_char(b)
    print(f"中文文本区内「单字 + FF」的串: {len(ones):,} 个\n")

    with_ptr = []
    without = []
    for off, body in ones:
        refs = ptr_sites(b, off)
        if refs:
            with_ptr.append((off, body, refs))
        else:
            without.append((off, body))

    print("=== 单字串的指针情况 ===")
    print(f"  有指针: {len(with_ptr):,}")
    print(f"  无指针: {len(without):,}")
    print()

    print("=== 有指针的单字串（前 15）===")
    changed = 0
    for off, body, refs in with_ptr[:15]:
        r0 = refs[0]
        old = struct.unpack_from("<I", a, r0)[0] if r0 + 4 <= len(a) else 0
        new = struct.unpack_from("<I", b, r0)[0] if r0 + 4 <= len(b) else 0
        mark = "已改指中文" if old != new else "未改"
        if old != new:
            changed += 1
        code_refs = [r for r in refs if r < CODE_END]
        print(f"  0x{off:06X}  {body.hex(' ')}  {len(refs)} 指针（代码段 {len(code_refs)}）")
        print(f"    @0x{r0:X}: 原版 0x{old:08X} → 汉化 0x{new:08X}  [{mark}]")
    print(f"\n  前 15 个中已改指中文: {changed}")

    # 全量统计指针是否都改了
    all_changed = 0
    all_same = 0
    for off, body, refs in with_ptr:
        any_change = False
        for r in refs:
            if r + 4 > len(a):
                continue
            if struct.unpack_from("<I", a, r)[0] != struct.unpack_from("<I", b, r)[0]:
                any_change = True
                break
        if any_change:
            all_changed += 1
        else:
            all_same += 1
    print(f"\n=== 全量：{len(with_ptr):,} 个有指针的单字串 ===")
    print(f"  至少一处指针被改成指中文: {all_changed:,} ({all_changed/max(len(with_ptr),1):.1%})")
    print(f"  指针全部未改:             {all_same:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
