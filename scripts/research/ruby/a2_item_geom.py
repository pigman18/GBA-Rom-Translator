#!/usr/bin/env python3
"""精确定位道具名表的 name_offset 与表基址。

已知：
  - 条目地址范围 0x39A670..0x39DC58
  - 与「0x39A648 + i*40 + 0x18」偏差恒为 +16
  - 所以实际 name_offset = 0x18 + 0x10 = 0x28？

但 0x28 > 0x18，且 40 - 0x28 = 16 字节字段宽。
需要验证：第 0 项地址 0x39A670 对应 i=0 还是 i=1。

用法：
    python scripts/research/ruby/a2_item_geom.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
GBA_BASE = 0x08000000


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    es = [e for e in d.get("entries") or [] if e.get("module") == "道具名"]
    addrs = []
    for e in es:
        try:
            a = int(str(e.get("address") or "").replace("0x", ""), 16)
        except ValueError:
            continue
        if a >= GBA_BASE:
            a -= GBA_BASE
        addrs.append(a)
    addrs.sort()

    print(f"道具名条目 {len(addrs)}，范围 0x{addrs[0]:06X}..0x{addrs[-1]:06X}\n")

    # 计算相邻差
    from collections import Counter
    gaps = Counter(b - a for a, b in zip(addrs, addrs[1:]))
    print("=== 相邻条目间距（前 8）===")
    for g, c in gaps.most_common(8):
        print(f"  {g} 字节: {c}")

    # 反推 entry_size
    print()
    print("=== 反推 entry_size ===")
    for step in (40, 44, 48, 56):
        ok = sum(1 for g, c in gaps.items() if g % step == 0 for _ in range(c))
        total = sum(gaps.values())
        if ok / total > 0.5:
            print(f"  step {step}: {ok}/{total} ({ok/total:.0%}) 的间距是其倍数")

    # 用最小地址反推
    first = addrs[0]
    print()
    print(f"=== 第 0 项地址 0x{first:06X} ===")
    print(f"  该地址前的字节（-48..+40）:")
    lo = max(0, first - 48)
    print(f"    0x{lo:06X}: {rom[lo:first + 40].hex(' ')}")

    # 找表基址：往前往回退，找第一个连续的名字序列起点
    print()
    print("=== 尝试不同 name_offset（以 first 为 i=0）===")
    for e_size in (40, 44, 48):
        for noff in range(0, e_size, 4):
            table = first - noff
            if table < 0:
                continue
            # 验证：所有 addrs 都能表示为 table + i*e_size + noff
            ok = 0
            for a in addrs:
                delta = a - table - noff
                if delta >= 0 and delta % e_size == 0:
                    ok += 1
            if ok == len(addrs):
                print(f"  ✅ entry_size={e_size} name_offset=0x{noff:X} "
                      f"table_base=0x{table:06X}  （全部 {len(addrs)} 条吻合）")
            elif ok / len(addrs) > 0.95:
                print(f"  ~ entry_size={e_size} name_offset=0x{noff:X} "
                      f"table_base=0x{table:06X}  （{ok}/{len(addrs)} 吻合）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
