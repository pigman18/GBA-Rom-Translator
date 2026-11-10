#!/usr/bin/env python3
"""A1：确认「00 67 <ptr>」是 ruby 的脚本内嵌文本引用。

上一脚本发现 NO_PTR 条目被非对齐位置引用：
  前字节 0x00: 2334 处
  前字节 0x08: 343 处
  前字节 0x67: 91 处

火红用 `02 67 <ptr>`（opcode + ptr）。ruby 可能是 `00 67 <ptr>`。
注意：0x67 在 ruby 常为 message/list op。

本脚本：抽取若干采样，打印完整上下文，确认是不是脚本 opcode 序列。

用法：
    python scripts/research/ruby/a1_script_confirm.py
"""
from __future__ import annotations

import json
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
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
OWN = ROOT / "work" / "_probe" / "a1_ownership.json"
GBA_BASE = 0x08000000


def main() -> int:
    rom = ROM_PATH.read_bytes()
    own = json.loads(OWN.read_text(encoding="utf-8"))
    no_ptr = own.get("NO_PTR") or []
    targets = {int(r["addr"].replace("0x", ""), 16) for r in no_ptr}

    refs: list[tuple[int, int]] = []   # (ref_off, target)
    n = len(rom) - 4
    for off in range(0, n):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            t = v - GBA_BASE
            if t in targets:
                refs.append((off, t))

    print(f"引用数 {len(refs):,}\n")

    # 按「前 2 字节」聚合
    prefix: Counter = Counter()
    for off, _t in refs:
        if off >= 2:
            prefix[rom[off - 2:off].hex()] += 1

    print("=== 引用位置前 2 字节（前 15）===")
    for p, c in prefix.most_common(15):
        print(f"  {p}: {c}")

    print()
    print("=== 样本上下文（前 20）===")
    shown = 0
    for off, t in refs:
        if shown >= 20:
            break
        # 只展示前 2 字节是 0067 / 0008 / 0068 这类脚本形态的
        pre = rom[off - 2:off].hex() if off >= 2 else "??"
        ctx = rom[max(0, off - 8):off + 12]
        print(f"  ref 0x{off:06X} (前2字节 {pre}) → 文本 0x{t:06X}")
        print(f"    ctx: {ctx.hex(' ')}")
        shown += 1

    # 统计：这些文本地址是否也在某个连续块内
    print()
    print("=== 引用位置按区域 ===")
    zone: Counter = Counter()
    for off, _t in refs:
        if off < 0x100000:
            zone["代码段 <0x100000"] += 1
        elif off < 0x1C0000:
            zone["ROM 0x100000-0x1C0000"] += 1
        elif off < 0x400000:
            zone["表区 0x1C0000-0x400000"] += 1
        else:
            zone["高地址"] += 1
    for z, c in zone.most_common():
        print(f"  {z:<26} {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
