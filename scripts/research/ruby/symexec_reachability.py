#!/usr/bin/env python3
"""看清「站点到底在哪个分支上」——决定符号执行要多分支还是单向。

判据：从函数入口按控制流走，能否到达 ldr 所在代码块？
如果走不到，说明该站点在 switch/条件分支的其它臂上，单向执行必然失败。

用法：
    python scripts/research/ruby/symexec_reachability.py
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
sys.path.insert(0, str(ROOT / "src"))

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

TABLES = [
    ("招式名",         0x1CACFC, 8),
    ("特性名",         0x1CBC44, 8),
    ("属性名",         0x1CBB0C, 5),
    ("道具名",         0x39A648, 40),
    ("图鉴分类名",     0x38474C, 28),
    ("秘密基地装饰名", 0x3C2A44, 28),
]


def find_ldrs(rom: bytes, base: int, back: int = 4096) -> list[int]:
    gba = base + 0x08000000
    needle = struct.pack("<I", gba)
    lits, s = [], 0
    while True:
        i = rom.find(needle, s)
        if i < 0:
            break
        if i % 4 == 0:
            lits.append(i)
        s = i + 1
    ldrs, seen = [], set()
    for lit in lits:
        for off in range(max(0, lit - back), lit, 2):
            hw = struct.unpack_from("<H", rom, off)[0]
            if (hw & 0xF800) != 0x4800:
                continue
            if ((off + 4) & ~3) + (hw & 0xFF) * 4 == lit:
                if off not in seen:
                    seen.add(off)
                    ldrs.append(off)
                break
    return sorted(ldrs)


def reachable(rom: bytes, entry: int, target: int,
              limit: int = 0x400) -> tuple[bool, int]:
    """从 entry 做 DFS（含 b / bcond 两条臂），能否到达 target 所在块。

    返回 (是否可达, 走了多少条指令)。target 认为在 [target-8, target+8] 内即命中。
    """
    seen: set[int] = set()
    stack = [entry]
    n = 0
    lo = entry
    hi = entry + limit

    while stack:
        pc = stack.pop()
        while lo <= pc < hi:
            if pc in seen:
                break
            seen.add(pc)
            if abs(pc - target) <= 8:
                return True, n
            n += 1
            ins = next(md.disasm(rom[pc:pc + 4], pc), None)
            if ins is None:
                break
            mn, ops = ins.mnemonic, ins.op_str
            if mn in ("bx", "bxns", "blx"):
                break
            if mn == "pop" and "pc" in ops:
                break
            if mn in ("b", "bcond", "bne", "beq", "bgt", "blt", "bge",
                      "ble", "bhi", "bls", "bcs", "bcc", "bmi", "bpl",
                      "bvs", "bvc"):
                # 解析目标
                tgt = None
                for tok in ops.replace(",", " ").split():
                    if tok.startswith("#"):
                        try:
                            v = int(tok[1:], 0)
                        except ValueError:
                            v = None
                        if v is not None:
                            tgt = v if v > 0x1000 else pc + 4 + v
                if mn == "b":
                    if tgt is not None:
                        pc = tgt
                        continue
                    break
                # 条件跳转：两条都探索
                if tgt is not None:
                    if lo <= tgt < hi:
                        stack.append(tgt)
                pc += 2
                continue
            pc += 2
    return False, n


def main() -> int:
    rom = ROM_PATH.read_bytes()
    from meowth.thumb_symexec import solve_site, find_function_start

    print(f"{'表':<16} {'ldr':>10} {'K':>5} {'可达':>5}  说明")
    print("-" * 78)
    n_ok = n_fail_reach = n_fail_other = 0
    for name, base, stride in TABLES:
        for ldr in find_ldrs(rom, base):
            r = solve_site(rom, ldr)
            entry = find_function_start(rom, ldr, limit=256)
            ok, _n = reachable(rom, entry, ldr)
            if r.stride is not None:
                n_ok += 1
                continue
            if not ok:
                n_fail_reach += 1
                tag = "不可达"
            else:
                n_fail_other += 1
                tag = "可达但失败"
            print(f"{name:<16} 0x{ldr:06X} {'?':>5} {'是' if ok else '否':>5}  {tag}")
    print("-" * 78)
    print(f"求解成功 {n_ok} / 目标不可达 {n_fail_reach} / 可达但失败 {n_fail_other}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
