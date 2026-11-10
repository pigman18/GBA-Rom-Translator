#!/usr/bin/env python3
"""逐条追踪一个站点的完整符号执行过程，看链在哪断。

选特性名 0x09C6C4（最简单，3 个站点里最规整的一个）：
  期望：在 0x09C6C6 的 `adds r0,r0,r1` 求到 K=8

用法：
    python scripts/research/ruby/symexec_trace.py
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"


def main() -> int:
    from meowth.thumb_symexec import (decode, Lin, BASE, UNKNOWN,
                                      find_function_start, Val)

    rom = ROM.read_bytes()
    ldr = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x09C6C4
    stride = int(sys.argv[2], 0) if len(sys.argv) > 2 else 8

    start = find_function_start(rom, ldr, limit=512)
    print(f"=== ldr@0x{ldr:06X}  函数入口 0x{start:06X}  期望 K={stride} ===")
    print()

    regs: dict[int, Val] = {i: UNKNOWN for i in range(16)}
    regs[0] = Lin(1)
    saved: list[dict] = []

    for off in range(start, min(len(rom) - 1, ldr + 32), 2):
        ins = decode(rom, off)
        if ins is None:
            continue
        mn = ins.mn
        note = ""

        if mn == "ldr_pc":
            regs[ins.rd] = BASE
            note = f"r{ins.rd}=BASE"
        elif mn in ("ldr", "ldrh", "ldrb", "ldr_reg", "ldrh_reg", "ldrb_reg"):
            regs[ins.rd] = Lin(1)
            note = f"r{ins.rd}=1*i（内存值）"
        elif mn == "movs_imm":
            regs[ins.rd] = Lin(0, ins.imm or 0)
            note = f"r{ins.rd}={ins.imm}"
        elif mn in ("movs", "mov_hi"):
            regs[ins.rd] = regs.get(ins.rs)
            note = f"r{ins.rd}=r{ins.rs}"
        elif mn in ("lsls", "lsrs", "asrs"):
            src = regs.get(ins.rs)
            if isinstance(src, Lin):
                if mn == "lsls":
                    regs[ins.rd] = src.lshift(ins.imm)
                    note = f"r{ins.rd}={src}<<{ins.imm}={regs[ins.rd]}"
                else:
                    r = src.rshift(ins.imm)
                    regs[ins.rd] = r if r is not None else UNKNOWN
                    note = f"r{ins.rd}={src}>>{ins.imm}={'None' if r is None else regs[ins.rd]}"
            else:
                regs[ins.rd] = UNKNOWN
                note = f"r{ins.rd}=UNKNOWN（源 r{ins.rs} 未知）"
        elif mn in ("adds", "subs"):
            a, b = regs.get(ins.rs), regs.get(ins.rn)
            if mn == "adds":
                hit = None
                for x, y in ((a, b), (b, a)):
                    if x == BASE and isinstance(y, Lin):
                        hit = y.a
                        break
                if hit is not None:
                    note = f"★★ 命中 base+index → K={hit}"
                    regs[ins.rd] = Lin(0)
                elif isinstance(a, Lin) and isinstance(b, Lin):
                    regs[ins.rd] = a.add(b)
                    note = f"r{ins.rd}={regs[ins.rd]}"
                else:
                    regs[ins.rd] = UNKNOWN
                    note = f"r{ins.rd}=UNKNOWN（r{ins.rs}={a} r{ins.rn}={b}）"
            else:
                if isinstance(a, Lin) and isinstance(b, Lin):
                    regs[ins.rd] = a.sub(b)
                    note = f"r{ins.rd}={regs[ins.rd]}"
                else:
                    regs[ins.rd] = UNKNOWN
                    note = "UNKNOWN"
        elif mn == "add_hi":
            a, b = regs.get(ins.rd), regs.get(ins.rn)
            hit = None
            for x, y in ((a, b), (b, a)):
                if x == BASE and isinstance(y, Lin):
                    hit = y.a
                    break
            if hit is not None:
                note = f"★★ hi 命中 → K={hit}"
            elif isinstance(a, Lin) and isinstance(b, Lin):
                regs[ins.rd] = a.add(b)
                note = f"r{ins.rd}={regs[ins.rd]}"
            elif isinstance(b, Lin):
                regs[ins.rd] = b
                note = f"r{ins.rd}=r{ins.rn}"
            else:
                regs[ins.rd] = UNKNOWN
                note = "UNKNOWN"
        elif mn in ("adds_imm", "subs_imm"):
            src = regs.get(ins.rd)
            if isinstance(src, Lin):
                d = ins.imm if mn == "adds_imm" else -ins.imm
                regs[ins.rd] = Lin(src.a, src.b + d)
                note = f"r{ins.rd}={regs[ins.rd]}"
            else:
                regs[ins.rd] = UNKNOWN
                note = "UNKNOWN"
        elif mn == "push":
            saved.append(dict(regs))
            note = "保存栈"
        elif mn == "pop":
            if saved:
                regs = saved.pop()
            note = "恢复栈"
        elif mn == "bl":
            regs[0] = UNKNOWN
            note = "r0=UNKNOWN（bl 返回值）"
        elif mn == "add_sp":
            regs[ins.rd] = UNKNOWN
            note = "UNKNOWN"

        # 只打印 ldr 附近
        if off >= ldr - 40 or note.startswith("★★"):
            live = " ".join(f"r{k}={v}" for k, v in sorted(regs.items())
                            if k < 8 and v is not None)
            print(f"  0x{off:06X} {mn:<10} {note:<32} | {live}")
        if note.startswith("★★"):
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
