#!/usr/bin/env python3
"""道具名：代码实际引用的基址到底是哪个？

矛盾：
  - ROM 结构：entry_size=40、name@+0x18，表结构起点 0x39A658（6/6 合法）
  - 但 0x0839A658 字面量 0 处；0x0839A648 有 14 处（全 ldr 确认）

两者差 0x10 = 16 字节。可能：
  A. 代码里的 base 指向「结构体数组的某个中间字段」
  B. 表其实从 0x39A648 开始，前 16 字节是「条目 -1」或表头
  C. 有两个不同用途的表

本脚本：从 0x39A648 起按 40 步长解析，看第 0 项和「偏移 -0x10」处分别是什么。

用法：
    python scripts/research/ruby/a2_item_base_truth.py
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
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
GBA_BASE = 0x08000000


def main() -> int:
    rom = ROM_PATH.read_bytes()

    print("=== 0x39A648..0x39A6D0 完整字节 ===")
    for r in range(0, 0x88, 8):
        off = 0x39A648 + r
        vals = struct.unpack_from("<2I", rom, off)
        print(f"  0x{off:06X}: {rom[off:off+8].hex(' ')}   "
              + "  ".join(f"0x{v:08X}" for v in vals))

    print()
    print("=== 两种解析对比 ===")
    for table, noff, label in ((0x39A648, 0x28, "代码 base 0x39A648, name@+0x28"),
                                (0x39A658, 0x18, "结构 base 0x39A658, name@+0x18")):
        print(f"\n  --- {label} ---")
        for i in range(4):
            base = table + i * 40
            name_at = base + noff
            seg = rom[name_at:name_at + 26]
            ff = seg.find(b"\xFF")
            body = seg[:ff] if ff >= 0 else seg
            print(f"    item{i} base=0x{base:06X} name@0x{name_at:06X}  "
                  f"{body.hex(' ')} ({len(body)}B)")

    # 关键：0x39A648 与 0x39A658 的差 0x10，看 0x39A648 处的 u32 是什么
    print()
    print("=== 0x39A648 处的 u32 ===")
    v = struct.unpack_from("<I", rom, 0x39A648)[0]
    print(f"  值 0x{v:08X}" + (f"  → 文件偏移 0x{v - GBA_BASE:06X}" if GBA_BASE <= v < 0x0A000000 else ""))

    print()
    print("=== 若 base=0x39A648，则每项 +0x28 是名字，那 +0x00..+0x27 是什么？===")
    for i in range(3):
        base = 0x39A648 + i * 40
        head = rom[base:base + 0x28]
        print(f"  item{i} 0x{base:06X}: {head.hex(' ')}")
        # 解析为 u32
        for k in range(0, 0x28, 4):
            v = struct.unpack_from("<I", rom, base + k)[0]
            is_ptr = GBA_BASE <= v < 0x0A000000
            print(f"    +0x{k:02X}: 0x{v:08X}" + (f"  → 0x{v-GBA_BASE:06X}" if is_ptr else ""))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
