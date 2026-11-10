#!/usr/bin/env python3
"""只读 ROM，定位招式名表的确切起点与结构。

前一支脚本全区间扫描被宝可梦名表（stride=6）淹没。
本脚本改用「已知招式名内容」做锚：
  火红/红宝石日文文本中，招式名表紧跟 species 表之后（gMoveNames 惯例），
  ruby 里 0x1CACFC / 0x1CAD04 附近就是它。

做法：
  1. 打印 0x1CAC00..0x1CB000 全部字节（带注释形式）
  2. 对每个候选 stride (6..16)，逐项找「FF 结尾后是否 00 填充」
  3. 找「项内全是合法日文字节 + FF 结尾」的最长连续段

用法：
    python scripts/research/ruby/probe_movenames_truth2.py
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
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"


def main() -> int:
    rom = ROM.read_bytes()

    print("=== 0x1CAC00..0x1CAD80 原始字节 ===")
    for off in range(0x1CAC00, 0x1CAD80, 16):
        print(f"  0x{off:06X}: " + rom[off:off + 16].hex(" "))

    print("\n=== 从 0x1CACFC 起，按 stride 解析前 12 项 ===")
    for stride in (5, 6, 7, 8, 9, 10, 13):
        print(f"\n  -- stride={stride} --")
        base = 0x1CACFC
        for i in range(12):
            off = base + i * stride
            seg = rom[off:off + stride]
            ff = seg.find(0xFF)
            desc = f"len={ff}" if ff >= 0 else "无FF"
            print(f"    项{i:>2} 0x{off:06X}: {seg.hex(' '):<{stride*3}} {desc}")

    print("\n=== 找「连续 FF 结尾项」的最自然切分（变长解析）===")
    for start in (0x1CACFC, 0x1CAD04, 0x1CAD00):
        off = start
        lens = []
        for _ in range(20):
            ff = rom.find(b"\xFF", off, off + 32)
            if ff < 0:
                break
            lens.append(ff - off)
            # 跳过 FF 与后续 00 填充
            p = ff + 1
            while p < len(rom) and rom[p] == 0x00:
                p += 1
            off = p
        print(f"  起点 0x{start:06X}: 项长序列 {lens}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
