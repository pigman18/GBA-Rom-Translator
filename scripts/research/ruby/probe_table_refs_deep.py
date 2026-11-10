#!/usr/bin/env python3
"""深挖：招式名/特性名 表到底被什么引用？（含裸偏移、近似基址、反汇编）

背景：
  上一轮我对 招式名 0x1CAD04 / 特性名 0x1CBC4C 报「0 处字面量」，
  就下了「内联、无锚点」的结论。但用户实测 SLT2 千条以上极卡，
  说明静态方案必须存在。可能是我搜索口径错了：
    - 只搜了 GBA 指针 0x081CAD04，没搜裸偏移 0x0001CAD04
    - 没搜「基址±邻域」的字面量
    - 没反汇编看真实加载指令

本脚本补齐这三种口径。

用法：
    python scripts/research/ruby/probe_table_refs_deep.py
"""
from __future__ import annotations

import json
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
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"

GBA_BASE = 0x08000000


def parse_hex(s) -> int:
    return int(str(s).replace("0x", "").replace("0X", ""), 16)


def sites_of(rom: bytes, value: int) -> list[int]:
    needle = struct.pack("<I", value)
    out, start = [], 0
    while True:
        i = rom.find(needle, start)
        if i < 0:
            break
        if i % 4 == 0:
            out.append(i)
        start = i + 1
    return out


def thumb_ldr_targets(rom: bytes, from_off: int, to_off: int):
    """枚举 [from,to) 内所有 thumb ldr rX,[pc,#imm]，返回 (指令偏移, 字面量偏移)。"""
    out = []
    for off in range(from_off, to_off, 2):
        hw = struct.unpack_from("<H", rom, off)[0]
        if (hw & 0xF800) != 0x4800:
            continue
        imm = (hw & 0xFF) * 4
        pc = (off + 4) & ~3
        out.append((off, pc + imm))
    return out


def main() -> int:
    rom = ROM.read_bytes()
    mods = (json.loads(TEXTS.read_text(encoding="utf-8")).get("modules") or {})

    for name in ("招式名", "特性名", "秘密基地装饰名", "属性名"):
        meta = mods.get(name)
        if not meta:
            continue
        start = parse_hex(meta["start"])
        read = meta.get("read") or {}
        noff = int(read.get("name_offset") or 0)
        base = start + noff

        print(f"=== {name} ===  名称字段基址 0x{base:06X}")

        # 口径 1：GBA 指针
        as_ptr = sites_of(rom, base + GBA_BASE)
        # 口径 2：裸偏移
        as_off = sites_of(rom, base)
        print(f"  [GBA指针 0x{base + GBA_BASE:08X}] 命中 {len(as_ptr)} 处"
              + (": " + ", ".join(f"0x{s:X}" for s in as_ptr[:8]) if as_ptr else ""))
        print(f"  [裸偏移 0x{base:08X}]        命中 {len(as_off)} 处"
              + (": " + ", ".join(f"0x{s:X}" for s in as_off[:8]) if as_off else ""))

        # 口径 3：基址 ±0x200 邻域内的 GBA 指针
        print(f"  邻域 ±0x200 内被引用的地址:")
        found_near = False
        for delta in range(-0x200, 0x201, 1):
            cand = base + delta
            if cand < 0 or cand > 0x7FFFFF:
                continue
            ss = sites_of(rom, cand + GBA_BASE)
            if ss:
                found_near = True
                print(f"    0x{cand:06X} (Δ{delta:+d}) × {len(ss)}  → "
                      + ", ".join(f"0x{s:X}" for s in ss[:4]))
                if delta > -0x200 + 40 and delta < 0x200 - 40:
                    continue
        if not found_near:
            print("    （无）")

        # 口径 4：ROM 里 0x08xxxxxx 形式的「指向本表附近」的指针总数
        cnt_near = 0
        for off in range(0, len(rom) - 4, 4):
            v = struct.unpack_from("<I", rom, off)[0]
            if GBA_BASE <= v < 0x0A000000:
                t = v - GBA_BASE
                if base - 0x1000 <= t <= base + 0x1000:
                    cnt_near += 1
        print(f"  ROM 内指向本表 ±0x1000 的指针总数: {cnt_near}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
