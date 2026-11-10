#!/usr/bin/env python3
"""道具名表几何的字节级确认：名称字段真正在哪。

候选（全部 281 条数学上吻合）：
  table=0x39A670 name_off=0x00
  table=0x39A658 name_off=0x18
  ...

必须用「名称字段后面跟的是什么」来定：若是 0xFF 结尾且后面接其他字段，
则名称字段起点可由 FC/FF 边界确定。

观察 0x39A658 起的字节：
  3f a6 39 08 | 00 00 01 04 | 79 56 0c 08 | 00 00 00 00 | 00 00 00 00 | 00 00 00 00 | 6f 5d 60 ae 9a ae 79 ff
                                                                    └──── 名称从这里？ ────┘

结构推测（entry_size=40）:
  +0x00 u32 指针 1
  +0x04 u32 标志/ID
  +0x08 u32 指针 2
  +0x0C u32 0
  +0x10 u32 0
  +0x14 u32 0
  +0x18 ... 名称？

但 0x39A658+0x18 = 0x39A670 = 第一个条目的地址。
若名称在 +0x18，那 0x39A670 是第 0 项名称，0x39A658 是第 0 项起点。

本脚本验证：从 0x39A658 按 40 步长解析，看每项 +0x18 是否是合法名字。

用法：
    python scripts/research/ruby/a2_item_confirm.py
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
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"


def main() -> int:
    rom = ROM_PATH.read_bytes()

    for table, noff in ((0x39A658, 0x18), (0x39A670, 0x00)):
        print(f"=== table=0x{table:06X} name_off=0x{noff:X} ===")
        ok = 0
        for i in range(6):
            base = table + i * 40
            name_at = base + noff
            seg = rom[name_at:name_at + 26]
            ff = seg.find(b"\xFF")
            body = seg[:ff] if ff >= 0 else seg
            # 合法名字：以 FF 结尾，长度 1..24
            valid = ff >= 1 and ff <= 24
            # 检查前 0x18 字节是否含 GBA 指针（结构体特征）
            head = rom[base:base + noff]
            has_ptr = any(
                0x08 <= head[k:k+4][3] <= 0x09 and head[k+3] != 0
                for k in range(0, max(1, len(head) - 3), 4)
            )
            if valid:
                ok += 1
            print(f"  item{i} base=0x{base:06X} name@0x{name_at:06X}")
            print(f"    head({len(head)}B): {head.hex(' ')}")
            print(f"    name: {body.hex(' ')}  ({len(body)}B, FF@{ff})"
                  + ("  ✅" if valid else "  ❌"))
        print(f"  合法项: {ok}/6")
        print()

    # 看 0x39A658 前面是什么
    print("=== 0x39A600..0x39A690 原始字节 ===")
    for r in range(0, 0x90, 16):
        print(f"  0x{0x39A600 + r:06X}: {rom[0x39A600+r:0x39A600+r+16].hex(' ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
