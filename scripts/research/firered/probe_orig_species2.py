#!/usr/bin/env python3
"""火红原版物种名表：用「代码引用的假名表」反查，不猜 stride。

方法：
  1. 收集汉化版里被改成指向新中文表（0x71F444）的那些代码位置
  2. 看这些位置在原版里指向哪里 —— 那就是原版物种名表
  3. 检查该处汉化是否改动

这是最可靠的路径：同一个代码位置，原版指 X，汉化指 0x71F444。

用法：
    python scripts/research/firered/probe_orig_species2.py
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
BASE_ZH = 0x71F444


def main() -> int:
    a = ORIG.read_bytes()
    b = ZH.read_bytes()

    needle = struct.pack("<I", BASE_ZH + GBA_BASE)
    sites = []
    s = 0
    while True:
        i = b.find(needle, s)
        if i < 0:
            break
        if i % 4 == 0:
            sites.append(i)
        s = i + 1

    print(f"汉化版里指向 0x{BASE_ZH:06X} 的 4 对齐位置: {len(sites)} 处\n")

    orig_targets: dict[int, int] = {}
    for off in sites:
        va = struct.unpack_from("<I", a, off)[0]
        vb = struct.unpack_from("<I", b, off)[0]
        orig_targets[va] = orig_targets.get(va, 0) + 1

    print("=== 这些位置在原版里指向哪（找原版物种名表）===")
    for va, cnt in sorted(orig_targets.items(), key=lambda kv: -kv[1]):
        is_ptr = GBA_BASE <= va < 0x0A000000
        tgt = va - GBA_BASE if is_ptr else None
        tag = f"0x{tgt:06X}" if tgt is not None else f"0x{va:08X}(非指针)"
        note = ""
        if tgt is not None:
            seg = a[tgt:tgt + 24]
            note = f"  原版内容: {seg.hex(' ')}"
        print(f"  {cnt:>2} 处 → {tag}{note}")

    print()
    print("=== 若找到原版表地址，检查汉化是否改动 ===")
    for va, cnt in sorted(orig_targets.items(), key=lambda kv: -kv[1]):
        if not (GBA_BASE <= va < 0x0A000000):
            continue
        tgt = va - GBA_BASE
        d = sum(1 for x, y in zip(a[tgt:tgt + 0x1000], b[tgt:tgt + 0x1000]) if x != y)
        print(f"  0x{tgt:06X}: 汉化差异 {d}/4096 ({d/4096:.1%})  "
              + ("✅ 原样保留" if d < 100 else "⚠️ 有改动"))
        # 该地址是否仍被代码引用
        n = struct.pack("<I", va)
        print(f"      原版引用 {a.count(n)} 处 → 汉化 {b.count(n)} 处")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
