#!/usr/bin/env python3
"""核对 TextsCurator 报告的两处几何错误（独立验证，不盲信）。

结论 1：树果名 entry_size 应为 28 而非 56，实际 43 条
结论 2：性格名真指针表在 0x3971E8（25 条），配置的 0x397168 是名字正文

用法：
    python scripts/research/ruby/verify_curator_claims.py
"""
from __future__ import annotations

import struct
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
GBA_BASE = 0x08000000


def main() -> int:
    rom = ROM_PATH.read_bytes()

    # ---- 结论 1：树果名 stride ----
    print("=== 结论 1：树果名 stride ===")
    BASE = 0x3A1050
    for stride in (28, 56):
        print(f"\n  -- 假定 stride={stride} --")
        for i in range(8):
            off = BASE + i * stride
            seg = rom[off:off + 16]
            ff = seg.find(b"\xFF")
            z = seg.find(b"\x00")
            end = min(x for x in (ff, z if z >= 0 else 99) if x >= 0)
            print(f"    i={i} 0x{off:06X}: {seg[:end + 1].hex(' '):<24} "
                  f"len={end}")

    # 用「每项都含 FF 结尾」判据对比
    print("\n  -- 合规率对比（项内 56B 里有 FF 结尾）--")
    for stride in (28, 56):
        ok = 0
        n = 60
        for i in range(n):
            off = BASE + i * stride
            if off + stride > len(rom):
                break
            seg = rom[off:off + stride]
            if b"\xFF" in seg:
                ok += 1
        print(f"    stride={stride}: {ok}/{n}")

    # ---- 结论 2：性格名指针表 ----
    print()
    print("=== 结论 2：性格名指针表位置 ===")
    for base, label in ((0x3971E8, "游标 0x3971E8"), (0x397168, "配置 0x397168")):
        print(f"\n  -- {label} --")
        ptr_cnt = 0
        for i in range(32):
            off = base + i * 4
            if off + 4 > len(rom):
                break
            v = struct.unpack_from("<I", rom, off)[0]
            is_ptr = GBA_BASE <= v < 0x0A000000
            if is_ptr:
                ptr_cnt += 1
            if i < 10 or (is_ptr and i < 28):
                print(f"    +{i*4:>2} 0x{off:06X}: 0x{v:08X}"
                      + (f" → 0x{v - GBA_BASE:06X}" if is_ptr else ""))
        print(f"    连续指针数: {ptr_cnt}/32")

    # 验证 0x3971E8 的 25 个指针指向哪
    print("\n  -- 0x3971E8 的指针指向 --")
    tgts = []
    for i in range(25):
        v = struct.unpack_from("<I", rom, 0x3971E8 + i * 4)[0]
        if GBA_BASE <= v < 0x0A000000:
            tgts.append(v - GBA_BASE)
    print(f"    {len(tgts)} 个指针，目标范围 "
          f"0x{min(tgts):06X}..0x{max(tgts):06X}" if tgts else "    无")
    if tgts:
        for i, t in enumerate(tgts[:5]):
            seg = rom[t:t + 12]
            ff = seg.find(b"\xFF")
            print(f"      [{i}] → 0x{t:06X}: {seg[:ff].hex(' ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
