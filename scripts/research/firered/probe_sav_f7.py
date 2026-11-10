#!/usr/bin/env python3
"""火红存档里的 F7 是什么？——核实「串档是否真的不乱」。

上一脚本发现汉化 sav 有 134 个 0xF7。需要区分：
  A. 0xF7 是宝可梦名字的编码 → 存档里存了中文 → 换回日版会乱码
  B. 0xF7 是其他数据碰巧等于 0xF7 → 无影响
  C. 存档是二进制的校验和/随机值

本脚本解析 sav 结构，定位 0xF7 所在的区块，判断其语义。

火红（第三代）存档结构：每个 section 4KB，共 14 section。
宝可梦数据在 PC box 区（各 section 的 offset 不同）。

用法：
    python scripts/research/firered/probe_sav_f7.py
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
SAV_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.sav"
SAV_ORIG = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.sav"

SECTION = 0x1000  # 4KB per section, 14 sections = 0xE000


def main() -> int:
    for path, tag in ((SAV_ORIG, "原版"), (SAV_ZH, "汉化")):
        if not path.is_file():
            print(f"{tag}: 不存在")
            continue
        s = path.read_bytes()
        print(f"=== {tag} sav {len(s):,} B ===")
        n_sec = len(s) // SECTION
        print(f"  按 {SECTION} 字节分 {n_sec} 段")

        # 统计每段里的 F7
        for i in range(min(n_sec, 36)):
            seg = s[i * SECTION:(i + 1) * SECTION]
            c = seg.count(b"\xF7")
            if c:
                pct = c / SECTION
                print(f"    section {i:>2} (0x{i:04X}000): 0xF7 × {c:>4} ({pct:.1%})")

        # 全局 F7 位置样本
        f7s = []
        i = 0
        while len(f7s) < 10:
            j = s.find(b"\xF7", i)
            if j < 0:
                break
            f7s.append(j)
            i = j + 1
        if f7s:
            print(f"  前 10 个 F7 偏移: " + ", ".join(f"0x{x:X}" for x in f7s))
            for x in f7s[:5]:
                ctx = s[max(0, x - 12):x + 16]
                print(f"    0x{x:05X}: {ctx.hex(' ')}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
