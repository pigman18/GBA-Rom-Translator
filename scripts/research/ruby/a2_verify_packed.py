#!/usr/bin/env python3
"""验证最终打包产物：6 张表数据 + 6 处 lsls + 字面量重定向是否都生效。

注意：流水线打包后 ROM 会重新对齐/扩容，位置可能变化，所以按
「表基址是否在第 6 张表数据的预期位置」判定，不硬编码文件偏移。

用法：
    python scripts/research/ruby/a2_verify_packed.py
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
PACKED = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
BUILD_OUT = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "build" / "output.gba"
ORIG = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
GBA_BASE = 0x08000000

LSLS = [
    ("招式名",         0x02B538, b"\x49\x01", "lsls r1,r1,#5"),
    ("特性名",         0x09C6C2, b"\x60\x01", "lsls r0,r4,#5"),
    ("属性名",         0x02B6AC, b"\x01\x01", "lsls r1,r0,#4"),
    ("道具名",         0x0A538C, b"\x00\x01", "lsls r0,r0,#4"),
    ("图鉴分类名",     0x08C1D4, b"\xC0\x00", "lsls r0,r0,#3"),
    ("秘密基地装饰名", 0x0AF2D6, b"\xC0\x00", "lsls r0,r0,#3"),
]

# (表名, 旧基址, stride, n, eos, name_offset, 首个字面量站点)
TABLES = [
    ("属性名",         0x1CBB0C, 17, 18,  0xFF, 0, 0x02B6F0),
    ("特性名",         0x1CBC44, 32, 77,  0xFF, 0, 0x09C700),
    ("秘密基地装饰名", 0x3C2A44, 56, 120, 0xFF, 1, 0x0AF2E8),
    ("道具名",         0x39A648, 80, 348, 0xFF, 0, 0x0A5398),
    ("招式名",         0x1CACFC, 32, 354, 0xFF, 0, 0x02B580),
    ("图鉴分类名",     0x38474C, 56, 386, 0x00, 0, 0x08C244),
]


def check(path: Path, label: str) -> tuple[int, int, int]:
    rom = path.read_bytes()
    print(f"\n{'=' * 70}")
    print(f"=== {label}  {len(rom):,} B ===")

    ok1 = 0
    for name, off, expect, desc in LSLS:
        actual = rom[off:off + 2]
        if actual == expect:
            ok1 += 1
        else:
            print(f"  ❌ {name} lsls: 期望 {expect.hex(' ')} 实际 {actual.hex(' ')}")
    print(f"  lsls 改动: {ok1}/{len(LSLS)}")

    ok2 = 0
    ok3 = 0
    for name, old_base, stride, n, eos, noff, lit in TABLES:
        # 从字面量读出新基址
        new_gba = struct.unpack_from("<I", rom, lit)[0]
        new_base = new_gba - GBA_BASE
        if not (0x08000000 <= new_gba < 0x0A000000):
            print(f"  ❌ {name}: 字面量 0x{new_gba:08X} 不是合法 GBA 地址")
            continue
        if new_base == old_base:
            print(f"  ❌ {name}: 字面量未改（仍指旧表 0x{new_gba:08X}）")
            continue
        ok3 += 1

        # 校验新表数据
        if new_base + stride * n > len(rom):
            print(f"  ❌ {name}: 新表 0x{new_base:06X} 超出 ROM")
            continue
        good = 0
        for i in range(n):
            seg = rom[new_base + i * stride + noff:
                      new_base + i * stride + noff + (stride - noff)]
            if eos in seg:
                good += 1
        if good == n:
            ok2 += 1
        else:
            print(f"  ⚠️ {name}: {good}/{n} 项含 eos")

    print(f"  表数据:   {ok2}/{len(TABLES)}")
    print(f"  字面量:   {ok3}/{len(TABLES)}")
    return ok1, ok2, ok3


def main() -> int:
    if not PACKED.is_file():
        sys.exit(f"打包产物不存在: {PACKED}")

    r1 = check(PACKED, "打包产物")
    if BUILD_OUT.is_file():
        print()
        r2 = check(BUILD_OUT, "armips 直出（对照）")
    else:
        r2 = (0, 0, 0)

    print()
    print("=" * 70)
    print("=== 结论 ===")
    a, b, c = r1
    if a == len(LSLS) and b == len(TABLES) and c == len(TABLES):
        print(f"  ✅ 打包产物全部通过：lsls {a}/6  表数据 {b}/6  字面量 {c}/6")
        return 0
    print(f"  ⚠️ 打包产物：lsls {a}/6  表数据 {b}/6  字面量 {c}/6")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
