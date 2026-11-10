#!/usr/bin/env python3
"""坐实：火红把定长名称表整张换成「指针数组 + 变长串」。

已发现候选：
  0x726124  354 元素 ← 恰好是招式数（火红 354 招式）
  0x71BFB4  251 元素
  0x71C404  135 元素
  0x71F234   79 元素
  0x711940   79 元素 ← 特性数 77~78

本脚本：
  1. 对每个候选数组，统计目标串长度分布（变长 ⇒ 长度不一）
  2. 对照原版同位置（全 FF ⇒ 新增的）
  3. 检查代码段是否有 ldr 引用该数组基址（即代码被改成读指针表）
  4. 验证「原版定长表是否还在原位」（在 ⇒ 保留；指针改道）

用法：
    python scripts/research/firered/probe_ptr_table_confirm.py
"""
from __future__ import annotations

import struct
import sys
from collections import Counter
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

# 已发现的候选指针数组（文件偏移, 元素数）
ARRAYS = [
    ("招式名?", 0x726124, 354),
    ("未知A",   0x71BFB4, 251),
    ("未知B",   0x71C404, 135),
    ("未知C",   0x71F234, 79),
    ("特性名?", 0x711940, 79),
]


def read_ptr_array(rom: bytes, off: int, n: int) -> list[int]:
    out = []
    for i in range(n):
        p = off + i * 4
        if p + 4 > len(rom):
            break
        v = struct.unpack_from("<I", rom, p)[0]
        if not (GBA_BASE <= v < 0x0A000000):
            break
        out.append(v - GBA_BASE)
    return out


def str_len(rom: bytes, off: int, cap: int = 64) -> int:
    seg = rom[off:off + cap]
    i = seg.find(b"\xFF")
    return i if i >= 0 else cap


def main() -> int:
    a = ORIG.read_bytes()
    b = ZH.read_bytes()
    print(f"origin / zh 各 {len(a):,} B\n")

    for name, off, n in ARRAYS:
        tgts = read_ptr_array(b, off, n)
        if not tgts:
            print(f"=== {name} @ 0x{off:06X} === 读不出指针\n")
            continue
        lens = [str_len(b, t) for t in tgts]
        lc = Counter(lens)
        # 原版同位置
        orig_bytes = a[off:off + 4 * min(len(tgts), 8)]
        all_ff = all(x == 0xFF for x in orig_bytes)

        print(f"=== {name} @ 0x{off:06X}  {len(tgts)} 元素 ===")
        print(f"  原版同位置全 FF: {all_ff}")
        print(f"  目标串长度分布: " + ", ".join(f"{l}B×{c}" for l, c in lc.most_common(6)))
        print(f"  长度唯一值 {len(lc)} 种 → " +
              ("变长（指针表特征）" if len(lc) > 3 else "接近定长"))
        # 数组内目标是否单调递增（连续排布）
        mono = all(y >= x for x, y in zip(tgts, tgts[1:]))
        print(f"  目标单调递增: {mono}")

        # 代码段是否引用该数组基址
        needle = struct.pack("<I", off + GBA_BASE)
        refs = []
        s = 0
        while True:
            i = b.find(needle, s)
            if i < 0:
                break
            if i % 4 == 0 and i < CODE_END:
                refs.append(i)
            s = i + 1
        print(f"  代码段引用该数组基址: {len(refs)} 处"
              + ("  " + ", ".join(f"0x{r:X}" for r in refs[:5]) if refs else ""))
        print()

    # 原版日文定长表（火红 gMoveNames 常见布局）是否还在
    print("=== 原版定长日文名表是否保留 ===")
    for label, lo, hi in (("0x3A0000..0x3C0000", 0x3A0000, 0x3C0000),
                          ("0x366000..0x36A000", 0x366000, 0x36A000)):
        d = sum(1 for x, y in zip(a[lo:hi], b[lo:hi]) if x != y)
        print(f"  {label}: 差异 {d}/{hi-lo} ({d/(hi-lo):.1%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
