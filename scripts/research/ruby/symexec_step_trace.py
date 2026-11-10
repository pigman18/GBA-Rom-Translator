#!/usr/bin/env python3
"""逐条打印符号执行状态（不猜，直接看）。

对指定站点，从函数入口起逐条指令打印：
  指令 / 解码结果 / 每条寄存器当前值 / 命中记录

用法：
    python scripts/research/ruby/symexec_step_trace.py 0x0A5432
    python scripts/research/ruby/symexec_step_trace.py 0x047808
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


def main() -> int:
    from meowth.thumb_symexec import (
        decode, Lin, BASE, UNKNOWN, find_function_start, Val,
    )

    rom = ROM_PATH.read_bytes()
    ldr_off = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x0A5432
    fwd = int(sys.argv[2], 0) if len(sys.argv) > 2 else 96

    start = find_function_start(rom, ldr_off, limit=256)
    hi = min(len(rom) - 1, ldr_off + fwd)

    print(f"=== ldr@0x{ldr_off:06X}  入口 0x{start:06X}  窗口尾 0x{hi:06X} ===")
    print()

    regs: dict[int, Val] = {i: UNKNOWN for i in range(16)}
    saved: list[dict] = []
    hits: list = []

    text = {i.address: i for i in md.disasm(rom[start:hi], start)}

    for off in range(start, hi, 2):
        ins = decode(rom, off)
        ins_text = ""
        if off in text:
            i = text[off]
            ins_text = f"{i.mnemonic} {i.op_str}"
        if ins is None:
            print(f"  0x{off:06X} {ins_text:<26} DECODE=None                    <-- 未处理")
            continue

        mn, note = ins.mn, ""
        before = {k: v for k, v in regs.items()}

        if mn == "ldr_pc":
            regs[ins.rd] = BASE
            note = f"r{ins.rd}=BASE"
        elif mn in ("ldr", "ldrh", "ldrb", "ldr_reg", "ldrh_reg", "ldrb_reg"):
            regs[ins.rd] = Lin(1)
            note = f"r{ins.rd}=Lin(1)"
        elif mn == "movs_imm":
            regs[ins.rd] = Lin(0, ins.imm or 0)
            note = f"r{ins.rd}=Lin(0,{ins.imm})"
        elif mn in ("movs", "mov_hi"):
            regs[ins.rd] = regs.get(ins.rs)
            note = f"r{ins.rd}=r{ins.rs}={regs.get(ins.rd)}"
        elif mn in ("lsls", "lsrs", "asrs"):
            src = regs.get(ins.rs)
            if isinstance(src, Lin):
                if mn == "lsls":
                    regs[ins.rd] = src.lshift(ins.imm, off=off, rd=ins.rd,
                                              rs=ins.rs)
                    note = f"r{ins.rd}={src}<<{ins.imm}={regs[ins.rd]}"
                else:
                    r = src.rshift(ins.imm, off=off, rd=ins.rd, rs=ins.rs)
                    regs[ins.rd] = r if r is not None else UNKNOWN
                    note = f"r{ins.rd}={r}"
            else:
                regs[ins.rd] = UNKNOWN
                note = f"r{ins.rd}=UNKNOWN (源 r{ins.rs}={src})"
        elif mn in ("adds", "subs"):
            a, b = regs.get(ins.rs), regs.get(ins.rn)
            if mn == "adds":
                hit = None
                for x, y in ((a, b), (b, a)):
                    if x == BASE and isinstance(y, Lin):
                        hit = y
                        break
                if hit is not None:
                    hits.append((off, hit.a, str(hit)))
                    note = f"★★命中 K={hit.a}"
                    regs[ins.rd] = Lin(0)
                elif isinstance(a, Lin) and isinstance(b, Lin):
                    regs[ins.rd] = a.add(b)
                    note = f"r{ins.rd}={regs[ins.rd]}"
                else:
                    regs[ins.rd] = UNKNOWN
                    note = (f"r{ins.rd}=UNKNOWN (r{ins.rs}={a},"
                            f" r{ins.rn}={b})")
            else:
                if isinstance(a, Lin) and isinstance(b, Lin):
                    regs[ins.rd] = a.sub(b)
                    note = f"r{ins.rd}={regs[ins.rd]}"
                else:
                    regs[ins.rd] = UNKNOWN
                    note = f"r{ins.rd}=UNKNOWN"
        elif mn == "add_hi":
            a, b = regs.get(ins.rd), regs.get(ins.rn)
            hit = None
            for x, y in ((a, b), (b, a)):
                if x == BASE and isinstance(y, Lin):
                    hit = y
                    break
            if hit is not None:
                hits.append((off, hit.a, str(hit)))
                note = f"★★命中 K={hit.a}"
                regs[ins.rd] = Lin(0)
            elif isinstance(a, Lin) and isinstance(b, Lin):
                regs[ins.rd] = a.add(b)
                note = f"r{ins.rd}={regs[ins.rd]}"
            elif isinstance(b, Lin):
                regs[ins.rd] = b
                note = f"r{ins.rd}={b}"
            else:
                regs[ins.rd] = UNKNOWN
                note = "r=UNKNOWN"
        elif mn in ("adds_imm", "subs_imm", "adds_imm3", "subs_imm3"):
            src = regs.get(ins.rn if mn.endswith("imm3") else ins.rd)
            if isinstance(src, Lin):
                d = (ins.imm or 0) * (1 if mn.startswith("adds") else -1)
                regs[ins.rd] = Lin(src.a, src.b + d, src.src, src.src_mn,
                                   src.src_imm, src.src_rd, src.src_rs)
                note = f"r{ins.rd}={regs[ins.rd]}"
            elif src == BASE:
                regs[ins.rd] = UNKNOWN
                note = f"r{ins.rd}=UNKNOWN  <-- ★BASE{'+' if mn.startswith('adds') else '-'}{ins.imm} 变 UNKNOWN"
            else:
                regs[ins.rd] = UNKNOWN
                note = f"r{ins.rd}=UNKNOWN"
        elif mn in ("push",):
            saved.append(dict(regs))
            note = "存栈"
        elif mn == "pop":
            if saved:
                regs = saved.pop()
            note = "复栈"
        elif mn == "bl":
            regs[0] = Lin(1)
            note = "r0=Lin(1) (bl返回值)"
        elif mn == "store" or mn == "str_sp" or mn == "cmp_imm":
            note = "（无影响）"
        elif mn in ("bcond", "b"):
            note = "（跳转，忽略）"
        elif mn == "add_sp":
            regs[ins.rd] = UNKNOWN
            note = f"r{ins.rd}=UNKNOWN"
        elif mn in ("bx", "hi_op"):
            note = "（返回，停止）"
        else:
            note = f"（未建模 {mn}）"

        # 值摘要
        live = " ".join(f"r{k}={v}" for k, v in sorted(regs.items())
                        if k < 13)
        kill = ""
        if off == ldr_off:
            kill = "   ★★★ 目标基址 ldr"
        print(f"  0x{off:06X} {ins_text:<26} {note:<34} | {live}{kill}")

        if mn == "bx":
            print("  --- bx 返回，停止 ---")
            break

    print()
    print(f"命中记录 {len(hits)}: {hits}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
