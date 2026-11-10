#!/usr/bin/env python3
"""火红是怎么处理定长表 stride 的？——实测它的招式名表访问代码。

用户的问题（2026-11-04）：
  「火红那边是怎么做的？我的理解应该是按原本的结构等长或等距改好，
    再改一个常量，旧的长或距应该能直接从编码里推算出来的吧」

要回答：
  1. 火红改 stride 了吗？改了几处？
  2. 火红是「改一个常量」还是「改多处乘法」？
  3. 火红的新旧 stride 各是多少？

方法：
  找火红 gMoveNames 的访问代码，看
  - 乘法形态（×stride）
  - 有几处站点
  - stride 值

用法：
    python scripts/research/ruby/firered_stride_how.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import capstone

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
FR_ORIG = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
FR_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
GBA_BASE = 0x08000000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

# 火红招式名表（前面调研已知：0x08204660 原版 / 0x0871F444 中文）
FR_MOVENAMES_ORIG = 0x204660
FR_ZH_TABLE = 0x71F444


def find_literals(rom: bytes, gba: int) -> list[int]:
    needle = struct.pack("<I", gba)
    out, s = [], 0
    while True:
        i = rom.find(needle, s)
        if i < 0:
            break
        if i % 4 == 0:
            out.append(i)
        s = i + 1
    return out


def find_ldr(rom: bytes, lit: int, back: int = 4096) -> list[int]:
    out = []
    for off in range(max(0, lit - back), lit, 2):
        hw = struct.unpack_from("<H", rom, off)[0]
        if (hw & 0xF800) != 0x4800:
            continue
        imm = (hw & 0xFF) * 4
        if ((off + 4) & ~3) + imm == lit:
            out.append(off)
    return out


def dump_before(rom: bytes, ldr: int, n: int = 16, label: str = "") -> None:
    print(f"    {label}ldr@0x{ldr:06X}:")
    lo = max(0, ldr - n)
    for ins in md.disasm(rom[lo:ldr + 8], lo):
        mark = ""
        if ins.address == ldr:
            mark = "  ★ 加载基址"
        elif ins.mnemonic in ("lsls", "lsl", "muls", "adds", "subs", "lsrs"):
            mark = "  ←"
        print(f"      0x{ins.address:06X}: {ins.mnemonic:<8}{ins.op_str}{mark}")


def main() -> int:
    a = FR_ORIG.read_bytes()
    b = FR_ZH.read_bytes()

    print("=" * 74)
    print("=== 火红招式名表：原版 vs 汉化 ===")
    print("=" * 74)

    for label, rom, base in (
        ("原版", a, FR_MOVENAMES_ORIG),
        ("汉化", b, FR_ZH_TABLE),
    ):
        gba = base + GBA_BASE
        lits = find_literals(rom, gba)
        ldrs = []
        for lit in lits:
            ldrs.extend(find_ldr(rom, lit))
        print(f"\n--- {label} base=0x{base:06X} ---")
        print(f"  字面量站点 {len(lits)}  ldr 引用 {len(ldrs)}")
        for ldr in ldrs[:3]:
            dump_before(rom, ldr, label=f"[{label}] ")

    # 关键对比：原版和汉化，改 stride 了吗？
    print()
    print("=" * 74)
    print("=== 关键：火红改 stride 了吗 ===")
    print("=" * 74)

    # 原版 ldr 序列
    orig_ldrs = []
    for lit in find_literals(a, FR_MOVENAMES_ORIG + GBA_BASE):
        orig_ldrs.extend(find_ldr(a, lit))
    zh_ldrs = []
    for lit in find_literals(b, FR_ZH_TABLE + GBA_BASE):
        zh_ldrs.extend(find_ldr(b, lit))

    print(f"  原版 ldr 站点: {len(orig_ldrs)}")
    print(f"  汉化 ldr 站点: {len(zh_ldrs)}")

    # 对比同位置代码
    print()
    print("  若汉化「改 stride」，这些站点的乘法指令应该变了。")
    print("  逐个对比原版/汉化在相同代码位置前后的字节：")
    for i, ldr_o in enumerate(orig_ldrs[:5]):
        before_o = a[max(0, ldr_o - 8):ldr_o]
        # 找汉化里对应位置（代码区地址不变，都在 0x08xxxxxx）
        before_z = b[max(0, ldr_o - 8):ldr_o]
        same = before_o == before_z
        print(f"    ldr@0x{ldr_o:06X}  原版 {before_o.hex(' ')}  "
              f"汉化 {before_z.hex(' ')}  {'相同' if same else '★不同'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
