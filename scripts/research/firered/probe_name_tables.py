#!/usr/bin/env python3
"""火红（日版汉化 2.2）定长名称表实测：结构 + 是否整表搬走。

用户疑问：火红的招式名/道具名这类定长表怎么做的？
要求：不能只看 ruby，必须实测火红原版 vs 汉化版的差异。

做法（origin-vs-translated 逐字节比对，AGENTS.md 要求的判据）：
  1. 找原版 POKEMON_FIRE_BPRJ00.gba 里的日文名表位置（用日文假名字节特征）
  2. 在汉化版同一位置看是否还在（在 → 原地改写；不在 → 搬走了）
  3. 统计汉化版里 F7 中文串所在区域，看是否形成新表

用法：
    python scripts/research/firered/probe_name_tables.py
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
ORIG = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"

GBA_BASE = 0x08000000


def find_seq(rom: bytes, seq: bytes, limit: int = 20) -> list[int]:
    out, start = [], 0
    while len(out) < limit:
        i = rom.find(seq, start)
        if i < 0:
            break
        out.append(i)
        start = i + 1
    return out


def main() -> int:
    if not ORIG.is_file() or not ZH.is_file():
        sys.exit(f"missing rom: orig={ORIG.is_file()} zh={ZH.is_file()}")
    a = ORIG.read_bytes()
    b = ZH.read_bytes()
    print(f"origin {len(a):,} B / translated {len(b):,} B\n")

    # 火红日文假名编码：pokeruby/firered 用 0x00-0xFF 的字符集，
    # 假名区 0x01-0x5F 左右。用已知招式名做锚：
    #   はたく (HA TAKU) / からてチョップ
    # 直接搜「火红中文 F7 串」更可靠：
    #   F7 hi lo 是中文前缀，连续 ≥2 个即中文名
    print("=== 汉化版中文串分布（F7 前缀）===")
    runs = []
    i = 0
    n = len(b) - 3
    while i < n:
        if b[i] == 0xF7 and b[i + 1] != 0xFF and b[i + 2] != 0xFF:
            start = i
            cnt = 0
            while i < n and b[i] == 0xF7:
                i += 3
                cnt += 1
                if cnt > 64:
                    break
            if cnt >= 2:
                runs.append((start, cnt))
        else:
            i += 1

    print(f"  ≥2 字中文串 {len(runs):,} 处")
    # 按区域聚合
    buckets: dict[int, int] = {}
    for off, _ in runs:
        buckets[off >> 16] = buckets.get(off >> 16, 0) + 1
    print("  按 64KB 区段聚合（前 15）:")
    for seg, cnt in sorted(buckets.items(), key=lambda kv: -kv[1])[:15]:
        print(f"    0x{seg:02X}0000..0x{seg:02X}F FFF  {cnt:>5} 串")

    # origin vs translated 差异集中在哪
    print("\n=== origin vs 汉化 差异统计 ===")
    same = 0
    diff_total = 0
    segs: dict[int, int] = {}
    step = 65536
    for base in range(0, min(len(a), len(b)), step):
        ca = a[base:base + step]
        cb = b[base:base + step]
        d = sum(1 for x, y in zip(ca, cb) if x != y)
        if d:
            segs[base] = d
            diff_total += d
        else:
            same += 1
    print(f"  不同字节总数 {diff_total:,} / {len(a):,} ({diff_total/len(a):.3%})")
    print("  差异最大的 12 个 64KB 段:")
    for base, d in sorted(segs.items(), key=lambda kv: -kv[1])[:12]:
        print(f"    0x{base:06X}..0x{base+step-1:06X}  差 {d:>6} B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
