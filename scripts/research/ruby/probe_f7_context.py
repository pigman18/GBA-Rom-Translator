#!/usr/bin/env python3
"""分别统计 0xF7 在「代码段」与「文本区」的分布，排除 Thumb 指令污染。

火红踩过的坑（FIRERED_FULL_LOGIC §1.2）：
  「代码段里的 60 F7 是 Thumb 的 b.n 指令，不是编码前缀」
  → 全 ROM 扫 F7 会被严重污染。

本脚本对 ruby 做同样的甄别：
  1. 代码段（<0x100000）的 F7 数
  2. 数据/文本区的 F7 数
  3. 已知文本表中的 F7（这是真正要关心的）
  4. 判断 0xF7 作为前缀是否安全

用法：
    python scripts/research/ruby/probe_f7_context.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ORIG = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

CODE_END = 0x100000          # 粗略代码段
# 已确认的文本表区（前面脚本验证过）
TEXT_ZONES = [
    ("宝可梦名", 0x1CA354, 412 * 6),
    ("招式名",   0x1CAD04, 354 * 8),
    ("特性名",   0x1CBC4C, 77 * 8),
    ("属性名",   0x1CBB0C, 18 * 5),
]


def main() -> int:
    rom = ORIG.read_bytes()
    print(f"ROM {len(rom):,} B\n")

    code_f7 = rom[:CODE_END].count(b"\xF7")
    data_f7 = rom[CODE_END:].count(b"\xF7")
    total = rom.count(b"\xF7")
    print("=== 0xF7 分布 ===")
    print(f"  代码段 <0x{CODE_END:X}      {code_f7:,}  ({code_f7/total:.1%})")
    print(f"  数据区 >=0x{CODE_END:X}     {data_f7:,}  ({data_f7/total:.1%})")
    print(f"  合计                    {total:,}")
    print()

    print("=== 已知文本表里的 0xF7 ===")
    for name, off, span in TEXT_ZONES:
        seg = rom[off:off + span]
        n = seg.count(b"\xF7")
        print(f"  {name:<8} 0x{off:06X}+{span:<6} 0xF7 出现 {n}")
    print()

    # 代码段里 F7 的上下文（判断是否 Thumb b.n）
    print("=== 代码段 0xF7 的前一字节分布（Thumb b.n = 0x60F7 / 0xD0F7 等）===")
    prev = Counter()
    i = 0
    while True:
        j = rom.find(b"\xF7", i, CODE_END)
        if j < 0:
            break
        if j > 0:
            prev[rom[j - 1]] += 1
        i = j + 1
    for b, c in prev.most_common(10):
        tag = ""
        if b in (0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67):
            tag = "  ← 疑似 b.n（Thumb 无条件跳转）"
        print(f"  前字节 0x{b:02X} × {c}{tag}")
    print()

    print("=== 结论判据 ===")
    print("  若文本表内 0xF7 = 0 且代码段 F7 多为 b.n → 0xF7 可安全作前缀")
    print("  但注意：现有 charmap 用 0x01 0xF7 表示全角空格，需一并处理")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
