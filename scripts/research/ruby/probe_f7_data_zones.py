#!/usr/bin/env python3
"""确认数据区 17,657 个 0xF7 是否落在真实文本流里。

四张已确认的名称表里 0xF7 = 0，但数据区还有 17,657 个。
若它们出现在会走文本打印的串里，0xF7 不能安全作前缀。

做法：
  1. 把数据区的 F7 按 64KB 段聚类，看集中在哪
  2. 对密集区抽样本，判断是不是「FF 结尾的文本串」结构
  3. 若是图形/音乐数据（无 FF 结尾规律），则不影响文本

用法：
    python scripts/research/ruby/probe_f7_data_zones.py
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

CODE_END = 0x100000


def main() -> int:
    rom = ORIG.read_bytes()
    print(f"ROM {len(rom):,} B\n")

    # 按 64KB 段统计
    buckets: Counter = Counter()
    for i in range(CODE_END, len(rom)):
        if rom[i] == 0xF7:
            buckets[i >> 16] += 1

    print("=== 数据区 0xF7 按 64KB 段分布（前 12）===")
    for seg, cnt in buckets.most_common(12):
        base = seg << 16
        pct = cnt / 65536
        print(f"  0x{base:06X}..0x{base+0xFFFF:06X}  {cnt:>5}  ({pct:.1%} of segment)")

    print("\n=== 密集段的样本（看是否 FF 结尾文本串）===")
    for seg, cnt in buckets.most_common(3):
        base = seg << 16
        print(f"\n  --- 0x{base:06X} ---")
        shown = 0
        i = base
        while i < base + 0x10000 and shown < 5:
            if rom[i] == 0xF7:
                # 找最近的 FF
                ff = rom.find(b"\xFF", i, i + 40)
                ctx = rom[max(base, i - 12):i + 16]
                print(f"    0x{i:06X}: ...{ctx.hex(' ')}...")
                if ff >= 0 and ff - i < 20:
                    print(f"             FF 距离 {ff - i} 字节 → 像文本串")
                else:
                    print("             40B 内无 FF → 不像文本串")
                shown += 1
                i += 16
            else:
                i += 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
