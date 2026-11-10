#!/usr/bin/env python3
"""统一：table_stride 改为直接用符号执行的结果。

问题：两个模块能力不一致
  thumb_symexec.solve_site    → 能算 K（特性名 3/3 全对）
  table_stride.rewrite_...    → 只识别 1/3（用自己的启发式）

修法：table_stride 内部调 solve_site，拿 K；
      若 K == old_stride，再定位「那条移位指令」并改写。

定位移位指令的方法：
  在 solve_site 的执行窗外，找「作用于 index 寄存器」的移位指令。
  更简单可靠：solve_site 已经知道 index 寄存器的值链，
  我们让它同时返回「产生该 K 的那条移位指令偏移」。

用法：
    python scripts/research/ruby/stride_unify.py
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

TABLES = [
    ("招式名",         0x1CACFC, 8),
    ("特性名",         0x1CBC44, 8),
    ("属性名",         0x1CBB0C, 5),
    ("道具名",         0x39A648, 40),
    ("图鉴分类名",     0x38474C, 28),
    ("秘密基地装饰名", 0x3C2A44, 28),
]


def main() -> int:
    """打印每站点：K 值 + 该 K 对应的移位指令位置。

    需要 solve_site 返回 insn_off，目前没返回，先验证「能否用 K 反查指令」。
    """
    from meowth.thumb_symexec import solve_site, decode
    from meowth.table_stride import find_ldrs
    import capstone

    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    rom = ROM.read_bytes()

    print(f"{'表':<16} {'ldr':>10} {'K':>6}  {'移位指令'}")
    print("-" * 70)

    for name, base, old_s in TABLES:
        for ldr in find_ldrs(rom, base):
            r = solve_site(rom, ldr)
            if r.stride is None or r.stride != old_s:
                continue
            # 在 ldr 前 24 字节内找移位指令，看哪条的 net 能凑出 K
            found = []
            lo = max(0, ldr - 24)
            for off in range(lo, ldr, 2):
                d = decode(rom, off)
                if d and d.mn in ("lsls", "lsrs", "asrs"):
                    ins = list(md.disasm(rom[off:off + 2], off))
                    txt = f"{ins[0].mnemonic} {ins[0].op_str}" if ins else "?"
                    found.append(f"0x{off:06X}:{txt}")
            print(f"{name:<16} 0x{ldr:06X} {r.stride:>6}  "
                  + (" | ".join(found) if found else "无移位"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
