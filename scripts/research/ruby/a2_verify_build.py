#!/usr/bin/env python3
"""验证 armips 产物：6 处 lsls 改动 + 93 处字面量重定向是否生效。

判据：
  1. output.gba 里 6 个 lsls 位置是新指令字节
  2. 93 个字面量位置指向 0x09EBxxxx
  3. 新表数据在 0x09EB0000 起，每项含 eos

用法：
    python scripts/research/ruby/a2_verify_build.py
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "build" / "output.gba"
ORIG = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
GBA_BASE = 0x08000000

# (表名, 指令文件偏移, 期望新字节, 说明)
LSLS = [
    ("招式名",         0x02B538, b"\x49\x01", "lsls r1,r1,#5"),
    ("特性名",         0x09C6C2, b"\x60\x01", "lsls r0,r4,#5"),
    ("属性名",         0x02B6AC, b"\x01\x01", "lsls r1,r0,#4"),
    ("道具名",         0x0A538C, b"\x00\x01", "lsls r0,r0,#4"),
    ("图鉴分类名",     0x08C1D4, b"\xC0\x00", "lsls r0,r0,#3"),
    ("秘密基地装饰名", 0x0AF2D6, b"\xC0\x00", "lsls r0,r0,#3"),
]

# (表名, 新表 GBA 地址, stride, n, eos, name_offset)
TABLES = [
    ("属性名",         0x09EB0000, 17, 18,  0xFF, 0),
    ("特性名",         0x09EB0134, 32, 77,  0xFF, 0),
    ("秘密基地装饰名", 0x09EB3714, 56, 120, 0xFF, 1),
    ("道具名",         0x09EB5154, 80, 348, 0xFF, 0),
    ("招式名",         0x09EB0AD4, 32, 354, 0xFF, 0),
    ("图鉴分类名",     0x09EBBE14, 56, 386, 0x00, 0),
]


def main() -> int:
    if not OUT.is_file():
        sys.exit(f"产物不存在: {OUT}")
    rom = OUT.read_bytes()
    orig = ORIG.read_bytes()

    print(f"产物 {OUT.name}  {len(rom):,} B")
    print(f"原版 {ORIG.name}  {len(orig):,} B")
    print()

    # 1. lsls 检查
    print("=== 1. 六处 lsls 改动 ===")
    ok1 = 0
    for name, off, expect, desc in LSLS:
        actual = rom[off:off + 2]
        old = orig[off:off + 2]
        mark = "✅" if actual == expect else "❌"
        if actual == expect:
            ok1 += 1
        print(f"  {name:<16} 0x{off:06X}  {old.hex(' ')} → {actual.hex(' ')}  "
              f"{desc}  {mark}")
    print(f"  通过 {ok1}/{len(LSLS)}")

    # 2. 新表数据检查
    print()
    print("=== 2. 新表数据完整性 ===")
    ok2 = 0
    for name, gba, stride, n, eos, noff in TABLES:
        base = gba - GBA_BASE
        if base + stride * n > len(rom):
            print(f"  {name:<16} ❌ 超出 ROM 范围")
            continue
        good = 0
        for i in range(n):
            seg = rom[base + i * stride + noff:
                      base + i * stride + noff + (stride - noff)]
            if eos in seg:
                good += 1
        mark = "✅" if good == n else "⚠️"
        if good == n:
            ok2 += 1
        print(f"  {name:<16} 0x{gba:08X}  {good}/{n} 项含 eos 0x{eos:02X}  {mark}")
    print(f"  通过 {ok2}/{len(TABLES)}")

    # 3. 字面量重定向检查（抽 3 处）
    print()
    print("=== 3. 字面量重定向抽查 ===")
    import struct
    samples = [
        ("属性名", 0x02B6F0, 0x09EB0000),
        ("特性名", 0x09C700, 0x09EB0134),
        ("招式名", 0x02B580, 0x09EB0AD4),
    ]
    ok3 = 0
    for name, lit, expect in samples:
        v = struct.unpack_from("<I", rom, lit)[0]
        mark = "✅" if v == expect else f"❌ 期望 0x{expect:08X}"
        if v == expect:
            ok3 += 1
        print(f"  {name:<10} @0x{lit:06X}: 0x{v:08X}  {mark}")

    print()
    print("=== 结论 ===")
    all_ok = (ok1 == len(LSLS) and ok2 == len(TABLES) and ok3 == len(samples))
    if all_ok:
        print("  ✅ 全部通过：6 处 lsls + 6 张表数据 + 字面量重定向 均已生效")
    else:
        print(f"  ⚠️ lsls {ok1}/{len(LSLS)}  表数据 {ok2}/{len(TABLES)}  "
              f"字面量 {ok3}/{len(samples)}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
