#!/usr/bin/env python3
"""道具名表定案：名称在条目 +0x00，entry_size=40，基址 0x39A658。

从字节看：
  item1 base=0x39A670: 6f 5d 60 ae 9a ae 79 ff ff 00 01 00 00 00 00 00 | dc 84 39 08 ...
                       └───── 名字 (7B) ─────┘ FF FF 后面是标志/指针

即每项结构（40B）:
  +0x00  名称（变长，FF 结尾）
  +0x??  填充/标志
  +0x10  u32 描述指针
  ...

所以 name_offset = 0，字段宽 = 40（整项）。

但注意：这些 40 字节的「项」是连续的，每项前都是名字。
那 0x39A648 那 14 处字面量是什么表？必须查清，否则会改错。

用法：
    python scripts/research/ruby/a2_item_final.py
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


def ldr_refs(rom: bytes, lit: int, back: int = 4096) -> list[int]:
    out = []
    for off in range(max(0, lit - back), lit, 2):
        hw = struct.unpack_from("<H", rom, off)[0]
        if (hw & 0xF800) != 0x4800:
            continue
        imm = (hw & 0xFF) * 4
        if ((off + 4) & ~3) + imm == lit:
            out.append(off)
    return out


def main() -> int:
    rom = ROM_PATH.read_bytes()

    # 1. 确认 name_offset=0 的解析
    print("=== 假设 base=0x39A658, entry_size=40, name@+0x00 ===")
    for i in range(5):
        base = 0x39A658 + i * 40
        seg = rom[base:base + 40]
        ff = seg.find(b"\xFF")
        name = seg[:ff] if ff >= 0 else seg
        print(f"  item{i} 0x{base:06X}: name={name.hex(' ')} ({len(name)}B, FF@{ff})")

    # 2. 0x39A648 那 14 处引用到底是什么表
    print()
    print("=== 0x0839A648 的 14 处字面量：所在函数在干什么 ===")
    pat = struct.pack("<I", 0x0839A648)
    sites = []
    s = 0
    while True:
        i = rom.find(pat, s)
        if i < 0:
            break
        if i % 4 == 0:
            sites.append(i)
        s = i + 1
    for lit in sites[:4]:
        ldrs = ldr_refs(rom, lit)
        print(f"  字面量 0x{lit:06X}" + (f"  ← ldr 0x{ldrs[0]:X}" if ldrs else ""))
        if ldrs:
            ldr = ldrs[0]
            # 该 ldr 前后的字节
            print(f"    前后: {rom[max(0,ldr-8):ldr+16].hex(' ')}")

    # 3. 关键：0x39A648 处是什么（已被 0xACACACAC 占据）
    print()
    print("=== 0x39A640..0x39A660 ===")
    print(f"  {rom[0x39A640:0x39A660].hex(' ')}")
    print("  ↑ 0x39A648 处是 AC AC AC AC（全角问号占位），不是表数据")
    print()
    print("  推测：代码用 0x39A648 作为「物种名/其他表」的基址，")
    print("        而道具名结构表实际从 0x39A658 开始。")
    print("        两者重叠 0x10 字节——需要确认是否有冲突。")

    # 4. 检查 0x39A658 - 40*1 = 0x39A630，看是否是合法 item
    print()
    print("=== 检查表是否从更早开始（i=-1, i=-2）===")
    for i in (-2, -1, 0):
        base = 0x39A658 + i * 40
        seg = rom[base:base + 40]
        ff = seg.find(b"\xFF")
        name = seg[:ff] if ff >= 0 else seg
        print(f"  item{i} 0x{base:06X}: {name.hex(' ')} ({len(name)}B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
