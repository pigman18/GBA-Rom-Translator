#!/usr/bin/env python3
"""定位火红原版日文招式名/道具名表，验证汉化版是否原地改写。

上一支脚本已证明：0x6D0000..0x730000 在原版是全 FF 空白区，
汉化版填满了中文 F7 串 → 中文文本全部写在新区。

本脚本回答：定长名称表本身怎么办？
  1. 用 pokeruby/firered 字符集把「はたく」编成字节，定位 gMoveNames
  2. 检查该地址在汉化版里是否被改写（原地）还是保持原样（搬走改指针）

火红字符集（pokeemerald/firered charmap）：
  'A'-'Z' = 0xBB-0xD4, 'a'-'z' = 0xD5-0xEE, '0'-'9' = 0xA1-0xAA
  空格 = 0x00, 0xFF = 终止
  仮名: ぁ=0x01 ... ん=0x30 左右；这里用「已知字符串实测定位」替代精确 charmap

做法：直接搜「FF 分隔、等距、≥300 项」的表候选，再核对内容是否日文假名区字节。

用法：
    python scripts/research/firered/probe_move_names.py
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


def find_stride_tables(rom: bytes, stride: int, min_items: int, lo: int, hi: int):
    """找「每 stride 字节末位为 FF」的连续块。"""
    out = []
    off = lo
    while off + stride * min_items < hi:
        run = 0
        p = off
        while p + stride <= hi and rom[p + stride - 1] == 0xFF:
            run += 1
            p += stride
            if run > 2000:
                break
        if run >= min_items:
            out.append((off, run))
            off = p
        else:
            off += 1
    return out


def main() -> int:
    a = ORIG.read_bytes()
    b = ZH.read_bytes()

    # 火红 gMoveNames 在 pokeruby 布局里通常紧邻 gSpeciesNames。
    # 先找「354 项、stride 13 且末字节 FF」的块（火红招式名 stride 13）
    print("=== 原版搜 stride=13 / 354 项 的候选（火红招式名布局）===")
    cands = find_stride_tables(a, 13, 300, 0x400000, 0x800000)
    for off, n in cands[:10]:
        print(f"  0x{off:06X}  {n} 项  stride=13")
        print(f"    原版: {a[off:off+52].hex(' ')}")
        print(f"    汉化: {b[off:off+52].hex(' ')}")
        d = sum(1 for x, y in zip(a[off:off+13*min(n,80)], b[off:off+13*min(n,80)]) if x != y)
        span = 13 * min(n, 80)
        print(f"    前 {min(n,80)} 项差异 {d}/{span} ({d/span:.0%})")
        print()

    print("=== 原版搜 stride=11 / ≥300 项（火红物种名布局）===")
    cands2 = find_stride_tables(a, 11, 300, 0x400000, 0x800000)
    for off, n in cands2[:6]:
        d = sum(1 for x, y in zip(a[off:off+11*min(n,80)], b[off:off+11*min(n,80)]) if x != y)
        span = 11 * min(n, 80)
        print(f"  0x{off:06X}  {n} 项  前{min(n,80)}项差异 {d}/{span} ({d/span:.0%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
