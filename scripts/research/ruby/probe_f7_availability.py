#!/usr/bin/env python3
"""确认 ruby 的 0xF7 字节是否可用于新的 F7 中文编码。

判据（必须全部成立）：
  1. 0xF7 在按 PCS 处理的路径上不会被当作有效字符绘制
  2. 原版 ROM 里 0xF7 实际出现在哪些语境（是否是控制码/假名）
  3. 我们现有产物里 0xF7 是否已被用作其他用途

背景：
  PrintNextChar_hook.c:161  `if (cur_char >= 0xF7u) return 1;`  ← 不可印位直接消费
  charmap.py:26             _DEFAULT_IDEOSPACE = bytes([0x01, 0xF7])
  说明 01 F7 这个两字节对可能是「全角空格」类的组合控制。

本脚本：
  A. 统计原版 ROM 里 0xF7 的出现次数与上下文
  B. 统计 01 F7 组合
  C. 统计我们产物 translated.gba 里的同项
  D. 判定 0xF7 能否独占为中文前缀

用法：
    python scripts/research/ruby/probe_f7_availability.py
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
OUT = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"


def stats(name: str, rom: bytes) -> dict:
    n_f7 = rom.count(b"\xF7")
    n_01f7 = rom.count(b"\x01\xF7")
    n_f9 = rom.count(b"\xF9")
    n_fa_ff = sum(rom.count(bytes([b])) for b in range(0xFA, 0x100))
    # 0xF7 后一字节分布（看是否像 3 字节前缀）
    nxt = Counter()
    i = 0
    while True:
        j = rom.find(b"\xF7", i)
        if j < 0 or j + 1 >= len(rom):
            break
        nxt[rom[j + 1]] += 1
        i = j + 1
    return {
        "name": name,
        "size": len(rom),
        "f7": n_f7,
        "01f7": n_01f7,
        "f9": n_f9,
        "fa_ff": n_fa_ff,
        "next_top": nxt.most_common(6),
    }


def main() -> int:
    for path in (ORIG, OUT):
        if not path.is_file():
            print(f"[skip] 不存在: {path.name}")
            continue
        rom = path.read_bytes()
        s = stats(path.name, rom)
        print(f"=== {s['name']}  {s['size']:,} B ===")
        print(f"  0xF7 出现     {s['f7']:,}")
        print(f"  0x01 0xF7 组合 {s['01f7']:,}")
        print(f"  0xF9 出现     {s['f9']:,}")
        print(f"  0xFA..0xFF    {s['fa_ff']:,}")
        print(f"  0xF7 后一字节分布（前6）: "
              + ", ".join(f"0x{b:02X}×{c}" for b, c in s["next_top"]))
        print()

    print("=== 解读 ===")
    print("  0xF7 极少出现且后随字节分散 → 大概率是控制码/未用位，可作前缀")
    print("  但必须排除 0x01 0xF7 是全角空格组合的情况")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
