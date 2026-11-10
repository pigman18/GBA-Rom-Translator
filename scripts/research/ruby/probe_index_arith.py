#!/usr/bin/env python3
"""反汇编：定长名称表的遍历是硬算 index*stride 还是读指针。

这决定「整表搬走改基址」能否直接放大表。
  硬算 index*stride → 搬走时 stride 必须保持，超长名字没地方放
  读每项指针       → 可以改成变长表

做法：对每个已确认的基址字面量，找引用它的 ldr 指令，
      向后反汇编 80 字节，检测是否出现
        lsls rX, rY, #3        (×8)
        lsls rX, rY, #2 / adds (×5 的常见形态：lsls#2 + adds)
        muls rX, rY, rZ
      以及随后的 adds rX, rX, rBase

用法：
    python scripts/research/ruby/probe_index_arith.py
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
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

GBA_BASE = 0x08000000
CODE_END = 0x100000

# (名称, 基址字面量所在文件偏移, 期望 stride)
SITES = [
    ("招式名",   0x02B580, 8),
    ("特性名",   0x09C700, 8),
    ("属性名",   0x02B6F0, 5),
    ("道具名",   0x0A5398, 40),
    ("图鉴分类名", 0x08C244, 28),
    ("秘密基地装饰名", 0x0AF2E8, 28),
    ("宝可梦名", 0x00CD74, 6),
]

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)


def find_ldr(rom: bytes, lit: int, back: int = 2048) -> list[int]:
    hits = []
    for off in range(max(0, lit - back), lit, 2):
        hw = struct.unpack_from("<H", rom, off)[0]
        if (hw & 0xF800) != 0x4800:
            continue
        imm = (hw & 0xFF) * 4
        if ((off + 4) & ~3) + imm == lit:
            hits.append(off)
    return hits


def analyze(rom: bytes, start: int, stride: int) -> dict:
    code = rom[start:start + 96]
    insns = list(md.disasm(code, start))
    res = {"mul_shift": [], "add_base": [], "ldr_ptr": []}
    base_reg = None
    for ins in insns[:26]:
        m, o = ins.mnemonic, ins.op_str
        if m in ("lsls", "lsl"):
            # lsls rX, rY, #3  → ×8
            if "#3" in o:
                res["mul_shift"].append((ins.address, f"{m} {o}", 8))
            elif "#2" in o:
                res["mul_shift"].append((ins.address, f"{m} {o}", 4))
            elif f"#{stride.bit_length() - 1}" in o and stride in (4, 8, 16):
                res["mul_shift"].append((ins.address, f"{m} {o}", stride))
        if m in ("muls", "mul"):
            res["mul_shift"].append((ins.address, f"{m} {o}", -1))
        if m in ("adds", "add") and o.count(",") == 2:
            parts = [p.strip() for p in o.split(",")]
            # adds rX, rX, rBase 形态
            if len(parts) == 3 and parts[0] == parts[1]:
                res["add_base"].append((ins.address, f"{m} {o}"))
        if m in ("ldr", "ldrh", "ldrb") and "pc" not in o:
            res["ldr_ptr"].append((ins.address, f"{m} {o}"))
    return res


def main() -> int:
    rom = ROM.read_bytes()
    print(f"ROM {len(rom):,} B   capstone {capstone.__version__}\n")

    for name, lit, stride in SITES:
        print(f"=== {name} ===  字面量 0x{lit:X}  期望 stride={stride}")
        ldrs = find_ldr(rom, lit)
        if not ldrs:
            print("  未找到 ldr 引用（可能不在代码段或被内联）\n")
            continue
        for ldr in ldrs[:2]:
            print(f"  ldr @ 0x{ldr:X}:")
            res = analyze(rom, ldr, stride)
            code = rom[ldr:ldr + 56]
            for ins in md.disasm(code, ldr):
                mark = ""
                s = f"{ins.mnemonic} {ins.op_str}"
                if any(a == ins.address for a, _, _ in res["mul_shift"]):
                    mark = "   ← 索引倍数"
                if any(a == ins.address for a, _ in res["add_base"]):
                    mark = "   ← 加基址"
                if any(a == ins.address for a, _ in res["ldr_ptr"]):
                    mark += "   ← 读内存"
                print(f"    0x{ins.address:06X}: {s}{mark}")
                if ins.address - ldr > 40:
                    break
            verdict = []
            if res["mul_shift"]:
                verdict.append(f"索引倍数 {len(res['mul_shift'])} 处")
            if res["add_base"]:
                verdict.append(f"基址相加 {len(res['add_base'])} 处")
            if res["ldr_ptr"]:
                verdict.append(f"读内存 {len(res['ldr_ptr'])} 处")
            print(f"    ⇒ {' / '.join(verdict) if verdict else '无明显模式'}")
            if res["mul_shift"] and res["add_base"]:
                print("    ⇒ 判定：硬算 index*stride（stride 不可变）")
            elif res["ldr_ptr"]:
                print("    ⇒ 判定：读指针/间接访问（可能可变形）")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
