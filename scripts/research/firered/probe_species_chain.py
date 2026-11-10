#!/usr/bin/env python3
"""火红宝可梦名「串档不乱」的完整链路 — 实测。

待查清的三件事：
  1. 0x0871F446 的中文名表被什么代码引用（谁读它）
  2. 原版 gSpeciesNames 在哪、是否被改写
  3. 存档里存的是什么编码（决定串档不乱的原因）

用法：
    python scripts/research/firered/probe_species_chain.py
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
ORIG = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"

GBA_BASE = 0x08000000
CODE_END = 0x200000
ZH_TABLE = 0x71F446


def find_refs(rom: bytes, gba: int, limit: int = 40) -> list[int]:
    needle = struct.pack("<I", gba)
    out, s = [], 0
    while len(out) < limit:
        i = rom.find(needle, s)
        if i < 0:
            break
        out.append(i)
        s = i + 1
    return out


def thumb_ldr_for(rom: bytes, lit: int, back: int = 2048) -> list[int]:
    hits = []
    for off in range(max(0, lit - back), lit, 2):
        hw = struct.unpack_from("<H", rom, off)[0]
        if (hw & 0xF800) != 0x4800:
            continue
        imm = (hw & 0xFF) * 4
        if ((off + 4) & ~3) + imm == lit:
            hits.append(off)
    return hits


def main() -> int:
    a = ORIG.read_bytes()
    b = ZH.read_bytes()

    print("=== 1. 中文名表 0x71F446 被谁引用 ===")
    for tag, rom in (("原版", a), ("汉化", b)):
        refs = find_refs(rom, ZH_TABLE + GBA_BASE)
        code_refs = [r for r in refs if r < CODE_END]
        print(f"  {tag}: 引用 {len(refs)} 处，其中代码段 {len(code_refs)} 处")
        for r in code_refs[:6]:
            ldrs = thumb_ldr_for(b if tag == "汉化" else a, r)
            extra = f"  ← ldr 0x{ldrs[0]:X}" if ldrs else ""
            print(f"    0x{r:06X}{extra}")
    print()

    # 中文名表是否从"名字表起始"被引用（可能引用的是表头更靠前的位置）
    print("=== 2. 中文名表附近哪些地址被代码引用（找真实表基址）===")
    hits = []
    for delta in range(-0x100, 0x40):
        cand = ZH_TABLE + delta
        refs = [r for r in find_refs(b, cand + GBA_BASE) if r < CODE_END]
        if refs:
            hits.append((cand, delta, refs))
    for cand, delta, refs in hits:
        print(f"  0x{cand:06X} (Δ{delta:+4d})  代码引用 {len(refs)}: "
              + ", ".join(f"0x{r:X}" for r in refs[:4]))
    print()

    print("=== 3. 中文名表前 96 字节（看结构）===")
    for r in range(0, 96, 24):
        print(f"  0x{ZH_TABLE + r:06X}: {b[ZH_TABLE + r:ZH_TABLE + r + 24].hex(' ')}")
    print()

    print("=== 4. 原版 vs 汉化：中文名表区域对比 ===")
    seg_a = a[ZH_TABLE:ZH_TABLE + 0x2000]
    seg_b = b[ZH_TABLE:ZH_TABLE + 0x2000]
    d = sum(1 for x, y in zip(seg_a, seg_b) if x != y)
    print(f"  0x{ZH_TABLE:06X}..+0x2000  差异 {d:,}/{0x2000} ({d/0x2000:.0%})")
    print(f"  原版非 FF 字节: {sum(1 for x in seg_a if x != 0xFF)}")
    print(f"  汉化非 FF 字节: {sum(1 for x in seg_b if x != 0xFF)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
