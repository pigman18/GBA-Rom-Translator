#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""枚举 ROM 里所有引用某常量的代码点（Thumb `ldr Rd,[pc,#imm]` 字面量池）。

用法: python scripts/find_literal_refs.py 0x03000328

输出：每个引用点地址 + 其后 0x60 字节反汇编，用于判定「该指针指向什么对象」。
"""
import os
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from dis_rom import dis  # noqa: E402


def main() -> int:
    val = int(sys.argv[1], 16)
    rom = open(os.path.join(ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba"),
               "rb").read()
    BASE = 0x08000000
    pat = struct.pack("<I", val)

    # 1) 找字面量池里的字节串
    lits = []
    i = rom.find(pat)
    while i != -1:
        lits.append(BASE + i)
        i = rom.find(pat, i + 1)
    print("字面量 0x%08X 在 ROM 中出现 %d 次" % (val, len(lits)))
    if not lits:
        return 1

    # 2) 找所有 `ldr Rd,[pc,#imm]` 指向这些字面量
    refs = []
    for a in range(BASE, BASE + len(rom) - 4, 2):
        hw = struct.unpack_from("<H", rom, a - BASE)[0]
        if (hw & 0xF800) != 0x4800:
            continue
        rd = (hw >> 8) & 7
        tgt = a + 4 + (hw & 0xFF) * 4
        if tgt in lits:
            refs.append((a, rd, tgt))
    # 字面量的「引用者」= 该点；同时把 str/ldr 该寄存器的点也列出
    print("引用点 %d 个：%s" % (len(refs), [hex(a) for a, _, _ in refs]))
    print()

    by = {}
    for a, rd, tgt in refs:
        by.setdefault(tgt, []).append((a, rd))

    for k, (lit, users) in enumerate(sorted(by.items())):
        print("=" * 78)
        print("字面量 #%d @0x%08X  被 %d 处引用: %s"
              % (k, lit, len(users), [(hex(a), "r%d" % rd) for a, rd in users]))
        print("=" * 78)
        lo = min(a for a, _ in users) - 0x40
        hi = max(a for a, _ in users) + 0x10
        lo = max(lo, BASE) & ~1
        print("--- 引用点上下文 ---")
        dis(lo, lit - lo + 4)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
