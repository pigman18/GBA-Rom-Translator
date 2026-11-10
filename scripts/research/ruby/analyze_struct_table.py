#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析一张结构体表：生成 field_map 需要的全部信息。

对给定表，输出：
  · entry 内每个字节偏移被哪些指令读过（反汇编）；
  · 建议的新布局（把一个字段留在原位，其余移到立即数可达处）；
  · stride 新旧倍率关系，以及需要改的乘法站点。

用法：
    python scripts/research/ruby/analyze_struct_table.py 秘密基地装饰名
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
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

# 表配置（与 emit_table_data.py 一致）
TABLES = {
    "图鉴分类名": dict(base=0x384746, stride=28, n=386, noff=6, usable=6),
    "秘密基地装饰名": dict(base=0x3C2A44, stride=28, n=120, noff=13, usable=10),
    "树果名": dict(base=0x3A1034, stride=28, n=43, noff=0, usable=10),
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in TABLES:
        print(__doc__)
        print("可用表：" + ", ".join(TABLES))
        return 3
    name = sys.argv[1]
    cfg = TABLES[name]
    base, stride, n = cfg["base"], cfg["stride"], cfg["n"]
    noff, usable = cfg["noff"], cfg["usable"]

    rom = ROM.read_bytes()
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

    print(f"=== {name}  base=0x{base:06X} stride={stride} n={n} "
          f"name@+{noff} usable={usable}")
    print()

    # 找引用这张表的字面量站点
    pat = struct.pack("<I", base + 0x08000000)
    sites = []
    i = rom.find(pat)
    while i != -1:
        if i % 4 == 0:
            sites.append(i)
        i = rom.find(pat, i + 1)

    print(f"基址字面量站点（4 对齐）: {len(sites)}")
    if not sites:
        print("  ★ 无站点：这张表可能通过别的基址（表头/偏移）访问，需先定位")
        return 0

    # 每个站点所在函数的字段访问
    accesses: dict[int, list[str]] = {}
    for s in sites:
        st = s
        for back in range(2, 0x40, 2):
            if (rom[s - back] & 0xFF) == 0xB5:
                st = s - back
                break
        offs = []
        for x in md.disasm(rom[st:st + 0x40], st + 0x08000000):
            o = x.op_str
            if x.mnemonic == "adds" and o.startswith("r"):
                parts = [p.strip() for p in o.split(",")]
                if len(parts) == 2 and parts[1].startswith("#"):
                    try:
                        offs.append((x.address, "adds", int(parts[1][1:], 0),
                                     parts[0]))
                    except ValueError:
                        pass
            if x.mnemonic in ("ldr", "ldrb", "ldrh") and "[r1" in o:
                if "#0x" in o:
                    try:
                        imm = int(o.split("#")[1].rstrip("]"), 16)
                        offs.append((x.address, x.mnemonic, imm, ""))
                    except ValueError:
                        pass
                elif o.endswith("[r1]"):
                    offs.append((x.address, x.mnemonic, 0, ""))
            if x.mnemonic == "bx":
                break
        if offs:
            accesses[st] = offs

    print(f"含字段访问的函数: {len(accesses)}")
    print()
    print(f"{'函数':<12}{'指令':<12}{'形式':<8}{'偏移':>6}  {'新偏移建议':>10}")
    print("-" * 62)
    seen_offs: set[int] = set()
    rows = []
    for st, offs in sorted(accesses.items()):
        for gba, mn, imm, reg in offs:
            seen_offs.add(imm)
            rows.append((st, gba, mn, imm))
            print(f"0x{st + 0x08000000:08X}  0x{gba:08X}  {mn:<8}0x{imm:02X}")
        print()

    print("被访问的偏移集合:", sorted(hex(x) for x in seen_offs))
    print()

    # 建议新布局：名字区扩大，字段塞进 ldrb 可达范围 + 保留一个在原位
    old_cap = usable
    # 目标 stride：下一个能容纳 4 汉字(17B)名字 + 全部字段的值
    need_name = 17
    print(f"名字区需要 {need_name}B（4 汉字），当前 {old_cap}B")
    print(f"字段占用的最高偏移: 0x{max(seen_offs | {0}):02X}")
    print()
    print("建议：stride 扩到能装下 name(17) + 全部字段，")
    print("      并把「最常访问且偏移最大」的字段留在原位，其余重排到 ≤31。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
