#!/usr/bin/env python3
"""机械判据验证：火红那 16 处 +1 有什么共同点？

候选判据（不需要理解语义）：
  判据 X：站点前方「最后一条移位指令」的源==目标（形如 lsls rX,rX,#n）
          且该 n 是 stride 的 2 的幂因子

  判据 Y：净移位 net 满足 stride % 2^net == 0

  判据 Z：把 ldr 前的移位指令「按寄存器分段」，找作用于 index 的那段

火红 16 处 +1 的详情（从 firered_judge.py 输出）：
  0x02FFDC: lsls#24 lsrs#24 lsls#3      → 最后一条 lsls#3
  0x04E790: lsls#1 lsls#3               → 最后一条 lsls#3
  0x06B66C: lsrs#16 lsls#16 lsls#2 lsrs#13 → 最后一条 lsrs#13
  0x09AEDE: ... lsls#16 lsrs#13         → 最后一条 lsrs#13
  0x0BEAE6: ... lsls#3                  → 最后一条 lsls#3
  0x0CDA72: lsls#8 lsls#16 lsrs#13      → 最后一条 lsrs#13
  0x0D954C: lsls#8 lsls#3               → 最后一条 lsls#3
  0x0E5D9E: lsls#16 lsrs#13             → 最后一条 lsrs#13
  0x0E60E0: lsls#1 lsls#1 lsls#3        → 最后一条 lsls#3
  0x114BD8: lsls#16 lsrs#13             → 最后一条 lsrs#13
  0x11CDCE: lsls#3                      → 最后一条 lsls#3
  0x125FB2: lsls#24 lsrs#24 lsls#3      → 最后一条 lsls#3
  0x126256: lsls#16 lsrs#13             → 最后一条 lsrs#13
  0x126336: lsls#16 lsrs#13             → 最后一条 lsrs#13
  0x126A32: ... lsrs#24 lsls#3          → 最后一条 lsls#3
  0x1325DA: lsls#16 lsrs#13             → 最后一条 lsrs#13

**观察：全是「ldr 前最后一条移位指令」！而且形态只有两种：
   lsls #3   （8 处的 2 的幂因子）
   lsrs #13  （配合前面的 lsls#16，净 3）**

⇒ 机械判据：**改「ldr 前最后一条移位指令」的立即数**。

验证这个判据在 ruby 上的效果。

用法：
    python scripts/research/ruby/stride_judge_last.py
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
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
GBA_BASE = 0x08000000

TABLES = [
    ("招式名",         0x1CACFC, 8,  16),
    ("特性名",         0x1CBC44, 8,  16),
    ("属性名",         0x1CBB0C, 5,  10),
    ("道具名",         0x39A648, 40, 80),
    ("图鉴分类名",     0x38474C, 28, 56),
    ("秘密基地装饰名", 0x3C2A44, 28, 56),
]


def last_shift_before(rom: bytes, ldr: int, back: int = 20):
    """返回 ldr 前最后一条移位指令 (off, mn, rd, rs, imm)，无则 None。"""
    best = None
    lo = max(0, ldr - back)
    for off in range(lo, ldr, 2):
        if off + 2 > len(rom):
            continue
        hw = struct.unpack_from("<H", rom, off)[0]
        mn = None
        if (hw & 0xF800) == 0x0000:
            mn = "lsls"
        elif (hw & 0xF800) == 0x0800:
            mn = "lsrs"
        elif (hw & 0xF800) == 0x1000:
            mn = "asrs"
        else:
            continue
        imm = (hw >> 6) & 0x1F
        if imm == 0:
            continue
        rs = (hw >> 3) & 0x07
        rd = hw & 0x07
        best = (off, mn, rd, rs, imm)
    return best


def find_ldrs(rom: bytes, base: int) -> list[int]:
    gba = base + GBA_BASE
    needle = struct.pack("<I", gba)
    lits, s = [], 0
    while True:
        i = rom.find(needle, s)
        if i < 0:
            break
        if i % 4 == 0:
            lits.append(i)
        s = i + 1
    ldrs = []
    for lit in lits:
        for off in range(max(0, lit - 4096), lit, 2):
            hw = struct.unpack_from("<H", rom, off)[0]
            if (hw & 0xF800) != 0x4800:
                continue
            imm = (hw & 0xFF) * 4
            if ((off + 4) & ~3) + imm == lit:
                ldrs.append(off)
                break
    return ldrs


def main() -> int:
    rom = ROM.read_bytes()

    print("=" * 78)
    print("=== 机械判据：改「ldr 前最后一条移位指令」 ===")
    print("=" * 78)
    print()
    print(f"{'表':<16} {'站点':>5} {'有移位':>7} {'形态':<30} {'可用'}")
    print("-" * 78)

    total = total_hit = 0
    for name, base, old_s, new_s in TABLES:
        ldrs = find_ldrs(rom, base)
        total += len(ldrs)
        hits = []
        forms = {}
        for ldr in ldrs:
            sh = last_shift_before(rom, ldr)
            if sh is None:
                continue
            _off, mn, _rd, _rs, imm = sh
            hits.append((ldr, sh))
            key = f"{mn}#{imm}"
            forms[key] = forms.get(key, 0) + 1

        total_hit += len(hits)
        ratio = new_s / old_s
        ok = ratio == int(ratio) and (int(ratio) & (int(ratio) - 1)) == 0

        form_s = ", ".join(f"{k}×{v}" for k, v in
                           sorted(forms.items(), key=lambda kv: -kv[1])[:3])
        print(f"{name:<16} {len(ldrs):>5} {len(hits):>7} {form_s:<30} "
              + ("✅" if ok else "❌非2幂"))

    print("-" * 78)
    print(f"{'合计':<16} {total:>5} {total_hit:>7}")
    print()
    print(f"覆盖率: {total_hit}/{total} = {total_hit / total:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
