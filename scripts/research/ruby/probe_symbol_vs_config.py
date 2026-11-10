#!/usr/bin/env python3
"""复核：ruby 名称表的「代码实际引用的基址」到底是哪一个。

上一支脚本（probe_table_base_literals.py）对 招式名 0x1CAD04 报 0 处字面量，
但符号表 gMoveNames = 0x081C8DC8（354×13），与配置地址不同。
必须先确认游戏代码读的是哪个表，否则「找不到锚点」的结论不可信。

本脚本：
  1. 对「符号表基址」和「配置基址」分别统计 u32 字面量引用
  2. 用 translate.build.json 作为文本判据，认出每个地址上是什么表
  3. 列出引用的具体位置，判断是否在代码段（< 0x100000）

用法：
    python scripts/research/ruby/probe_symbol_vs_config.py
"""
from __future__ import annotations

import json
import re
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
SYM = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "symbols" / "pokeruby_jp.sym"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"

GBA_BASE = 0x08000000
CODE_END = 0x100000  # 0x08000000..0x08100000 基本是代码


def parse_syms() -> dict[str, tuple[int, int]]:
    out: dict[str, tuple[int, int]] = {}
    pat = re.compile(r"^([0-9A-Fa-f]{8})\s+\S\s+([0-9A-Fa-f]{8})\s+(\S+)")
    for line in SYM.read_text(encoding="utf-8", errors="replace").splitlines():
        m = pat.match(line)
        if not m:
            continue
        addr = int(m.group(1), 16)
        size = int(m.group(2), 16)
        name = m.group(3)
        out.setdefault(name, (addr, size))
    return out


def literal_sites(rom: bytes, gba_addr: int) -> list[int]:
    needle = struct.pack("<I", gba_addr)
    sites, start = [], 0
    while True:
        i = rom.find(needle, start)
        if i < 0:
            break
        sites.append(i)
        start = i + 1
    return sites


def main() -> int:
    rom = ROM.read_bytes()
    syms = parse_syms()
    data = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = data.get("entries") or []

    by_addr: dict[int, dict] = {}
    for e in entries:
        try:
            a = int(str(e.get("address") or "0x0").replace("0x", ""), 16)
        except ValueError:
            continue
        if a >= GBA_BASE:
            a -= GBA_BASE
        by_addr[a] = e

    print(f"ROM {len(rom):,} B / symbols {len(syms):,}\n")

    # 关注的符号 + 配置起始
    probes = [
        ("gSpeciesNames(符号)", "gSpeciesNames", 0x1CA354),
        ("宝可梦名(配置)", None, 0x1CA354),
        ("gMoveNames(符号)", "gMoveNames", 0x1CAD04),
        ("招式名(配置)", None, 0x1CAD04),
        ("gAbilityNames(符号)", "gAbilityNames", 0x1CBC4C),
        ("特性名(配置)", None, 0x1CBC4C),
        ("属性名(配置)", None, 0x1CBB0C),
        ("gTypeNames(符号)", "gTypeNames", None),
    ]

    seen = set()
    for label, symname, cfg in probes:
        sym_addr = None
        if symname and symname in syms:
            sym_addr, sym_size = syms[symname]
            sym_addr -= GBA_BASE
        else:
            sym_size = 0

        for tag, foff in (("符号", sym_addr), ("配置", cfg)):
            if foff is None or foff in seen:
                continue
            seen.add(foff)
            sites = literal_sites(rom, foff + GBA_BASE)
            code_sites = [s for s in sites if s < CODE_END]
            e = by_addr.get(foff)
            sample = (e.get("original") if e else None)
            print(f"{label:<20} {tag} 0x{foff:06X}  字面量 {len(sites):>3} 处"
                  f"（代码段 {len(code_sites)}）  样本文本 {sample!r}")
            if code_sites[:6]:
                print(f"{'':24}代码段: " + ", ".join(f"0x{s:X}" for s in code_sites[:6]))
            if sites and not code_sites:
                print(f"{'':24}非代码段: " + ", ".join(f"0x{s:X}" for s in sites[:6]))
        print()

    # 属性名元素字面量是否连续（判断是否指针数组）
    print("=== 属性名 元素字面量位置 ===")
    for k in range(6):
        a = 0x1CBB0C + k * 5
        sites = literal_sites(rom, a + GBA_BASE)
        print(f"  元素{k} 0x{a:06X}: " + (", ".join(f"0x{s:X}" for s in sites[:4]) or "无"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
