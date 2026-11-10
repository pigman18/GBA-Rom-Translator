#!/usr/bin/env python3
"""texts_58: 溯源代码段 0xE6000..0xE6E00 —— 谁在用 0x3B3E64 这张表。

texts_57 发现 9 处对齐字面量引用 0x083B3E64，全在 0xE6058..0xE6D24。
这是一段连续的代码区（ARM/Thumb），需要看它干什么。

方法：
  1. 反汇编那段代码（用项目自带的 objdump，若有）
  2. 看 0xE6058 附近的指令模式：是否 ldr rX, [pc, #n] 取表地址
  3. 查符号表 0xE6000..0xE7000 有什么函数名

用法: python scripts/research/ruby/texts_58_code_trace.py
"""
from __future__ import annotations

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
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
SYM = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "symbols" / "pokeruby_jp.sym"
BASE = 0x08000000

REFS = [0xE6058, 0xE61C4, 0xE62F4, 0xE63F8, 0xE66EC, 0xE67BC, 0xE68D4, 0xE6A50, 0xE6D24]


def load_syms() -> list[tuple[int, str]]:
    out = []
    if not SYM.exists():
        return out
    for line in SYM.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            a = int(parts[0], 16)
        except ValueError:
            continue
        name = next((p for p in parts[2:] if not p.startswith("0") and p not in ("g", "l", "a")), "")
        out.append((a - BASE if a >= BASE else a, name))
    out.sort()
    return out


def main() -> int:
    rom = ROM_PATH.read_bytes()
    syms = load_syms()

    print("=" * 112)
    print("1) 符号表 0xE4000..0xE8000")
    print("=" * 112)
    seg = [(a, n) for a, n in syms if 0xE4000 <= a < 0xE8000]
    if seg:
        for a, n in seg:
            print(f"  0x{a:06X}  {n}")
    else:
        print("  无符号")

    # 每个引用点最近的符号
    print()
    print("=" * 112)
    print("2) 每个字面量引用点最近的符号函数")
    print("=" * 112)
    for r in REFS:
        prev = None
        for a, n in syms:
            if a <= r:
                prev = (a, n)
            else:
                break
        if prev and n:
            print(f"  0x{r:06X}  字面量  →  最近符号 0x{prev[0]:06X} {prev[1]} "
                  f"(+0x{r - prev[0]:X})")
        else:
            print(f"  0x{r:06X}  字面量  →  最近符号 0x{prev[0]:06X} {prev[1] if prev else '?'}")

    print()
    print("=" * 112)
    print("3) 引用点上下文（前后 24 字节，看 ldr 取址模式）")
    print("=" * 112)
    for r in REFS[:4]:
        ctx = rom[max(0, r - 12):r + 12]
        print(f"\n  0x{r:06X}:")
        print(f"    {ctx.hex(' ')}")
        # Thumb 16-bit 指令粗解
        for k in range(0, len(ctx) - 1, 2):
            w = struct.unpack_from("<H", ctx, k)[0] | 0
            addr = max(0, r - 12) + k
            note = ""
            if (w & 0xF800) == 0x4800:
                rt = (w >> 8) & 7
                imm = (w & 0xFF) * 4
                target = ((addr + 4) & ~3) + imm
                note = f"  LDR r{rt}, [pc,#{imm}] -> 0x{target:06X}"
                if base_ok(target):
                    v = struct.unpack_from("<I", rom, target)[0] if target + 4 <= len(rom) else 0
                    note += f"  = 0x{v:08X}"
            print(f"      0x{addr:06X}: {w:04X}{note}")

    return 0


def base_ok(t: int) -> bool:
    return 0 <= t < 0x800000


if __name__ == "__main__":
    raise SystemExit(main())
