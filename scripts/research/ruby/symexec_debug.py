#!/usr/bin/env python3
"""调试符号执行器：单步打印寄存器状态，看哪里断了。

以特性名 0x09C6C4 为例（形态最简单）：
  0x09C6BC: adds r4, r0, #0      r4 = r0（block 返回值）
  0x09C6BE: lsls r4, r4, #0x18   r4 <<= 24
  0x09C6C0: lsrs r4, r4, #0x18   r4 >>= 24
  0x09C6C2: lsls r0, r4, #3      r0 = r4*8   ★ stride
  0x09C6C4: ldr  r1, [pc, #0x38] r1 = BASE
  0x09C6C6: adds r0, r0, r1      r0 = index*8 + BASE   ★ 应在此判定

预期：在 0x09C6C6 求到 K=8。

用法：
    python scripts/research/ruby/symexec_debug.py
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
sys.path.insert(0, str(ROOT / "src"))

ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
GBA_BASE = 0x08000000

CASES = [
    ("特性名", 0x09C6C4, 8),
    ("招式名", 0x02B53A, 8),
    ("道具名", 0x0A538E, 40),
]


def main() -> int:
    from meowth.thumb_symexec import decode, Lin, BASE, UNKNOWN

    rom = ROM.read_bytes()

    for name, ldr, stride in CASES:
        print("=" * 76)
        print(f"=== {name} ldr@0x{ldr:06X} 旧stride={stride} ===")
        print("=" * 76)

        back = 64
        lo = max(0, ldr - back)
        hi = min(len(rom) - 1, ldr + 24)
        regs: dict = {i: UNKNOWN for i in range(16)}
        stack = []

        for off in range(lo, hi, 2):
            raw = rom[off:off + 2]
            ins = decode(rom, off)
            if ins is None:
                continue
            if ins.mn == "ldr" and ins.is_pc_ldr:
                regs[ins.rd] = BASE
            elif ins.mn in ("ldr", "ldrh", "ldrb") and ins.rn is not None:
                regs[ins.rd] = Lin(1)
            elif ins.mn == "ldr_reg":
                regs[ins.rd] = Lin(1)
            elif ins.mn == "movs" and ins.rs is None:
                regs[ins.rd] = Lin(0, ins.imm or 0)
            elif ins.mn == "movs" and ins.rs is not None:
                regs[ins.rd] = regs.get(ins.rs)
            elif ins.mn in ("lsls", "lsrs", "asrs") and ins.rs is not None:
                src = regs.get(ins.rs)
                if isinstance(src, Lin):
                    regs[ins.rd] = (src.lshift(ins.imm) if ins.mn == "lsls"
                                    else src.rshift(ins.imm))
                else:
                    regs[ins.rd] = UNKNOWN
            elif ins.mn == "adds" and ins.rs is not None and ins.rn is not None:
                a, b = regs.get(ins.rs), regs.get(ins.rn)
                if a == BASE and isinstance(b, Lin):
                    print(f"  ★★ 0x{off:06X} base+index → K={b.a}  ({b})")
                    break
                if b == BASE and isinstance(a, Lin):
                    print(f"  ★★ 0x{off:06X} base+index → K={a.a}  ({a})")
                    break
                if isinstance(a, Lin) and isinstance(b, Lin):
                    regs[ins.rd] = a.add(b)
                else:
                    regs[ins.rd] = UNKNOWN
            elif ins.mn == "adds_imm":
                src = regs.get(ins.rd)
                regs[ins.rd] = (Lin(src.a, src.b + ins.imm)
                                if isinstance(src, Lin) else UNKNOWN)
            elif ins.mn == "bl":
                regs[0] = Lin(1)

            # 打印
            if off >= ldr - 16:
                vals = {k: v for k, v in regs.items()
                        if v not in (UNKNOWN,) and k < 8}
                vs = " ".join(f"r{k}={v}" for k, v in sorted(vals.items()))
                print(f"  0x{off:06X} {raw.hex()} {ins.mn:<9}"
                      f"{ins.rd if ins.rd is not None else '-'}  {vs}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
