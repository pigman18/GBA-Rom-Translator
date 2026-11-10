#!/usr/bin/env python3
"""火红定长名称表：原地改写还是整表搬走？逐表实测。

用户质疑「ruby 走内联会非常慢」，要求给出火红的真实做法。
上一支脚本显示火红 0x6D0000..0x730000 整段被换成中文（约 600KB 改动）。

本脚本验证：
  1. 原版 0x6D0000..0x730000 是什么（日文名表？）
  2. 汉化版同地址是否仍是「同结构同位置」的表（原地改写）
     还是变成了完全不同的内容（搬走 + 原区废弃）
  3. 找具体招式名/道具名表的地址在两边是否一致

判据：如果汉化版同地址仍有「等距项的 FF 分隔名字表」→ 原地改写
      如果原地址变成乱码/空洞 → 搬走了

用法：
    python scripts/research/firered/probe_name_tables2.py
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
ORIG = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"

# 火红日文文本区（FIRERED_FULL_LOGIC 提到旧值集中在 0x083DDxxx）
SEGMENTS = [
    (0x6D0000, 0x10000, "中文主区 A"),
    (0x6F0000, 0x10000, "中文主区 B"),
    (0x700000, 0x10000, "中文主区 C"),
    (0xAF0000, 0x10000, "中文区 D"),
    (0x9B0000, 0x10000, "差异区 E"),
    (0x3DD000, 0x1000, "原版日文文本区(3DDxxx)"),
]


def describe(buf: bytes, off: int, n: int = 48) -> str:
    chunk = buf[off:off + n]
    return chunk.hex(" ")


def count_table_like(buf: bytes, off: int, span: int) -> tuple[int, int]:
    """统计区间内 FF 结尾项数 与 F7 前缀项数。"""
    seg = buf[off:off + span]
    ff = seg.count(b"\xFF")
    f7 = 0
    i = 0
    while i < len(seg) - 2:
        if seg[i] == 0xF7:
            f7 += 1
            i += 3
        else:
            i += 1
    return ff, f7


def main() -> int:
    a = ORIG.read_bytes()
    b = ZH.read_bytes()
    print(f"origin / translated 都 {len(a):,} B\n")

    for off, span, label in SEGMENTS:
        print(f"=== {label}  0x{off:06X} (+0x{span:X}) ===")
        for tag, buf in (("原版", a), ("汉化", b)):
            ff, f7 = count_table_like(buf, off, span)
            print(f"  {tag}  FF 数 {ff:>6}   F7 数 {f7:>6}   前 32B: {describe(buf, off, 32)}")
        # 同地址前 256 字节差异比例
        ca, cb = a[off:off + 256], b[off:off + 256]
        d = sum(1 for x, y in zip(ca, cb) if x != y)
        print(f"  前 256B 差异 {d}/256 ({d/256:.0%})")
        print()

    # 关键：找原版招式名表。火红日版「はたく」的编码需先确定字符集。
    # 换个稳妥办法：原版里找「FF 分隔、项长 8~13、连续 ≥100 项」的表
    print("=== 原版里搜「等距 FF 分隔名字表」候选 ===")
    for stride_guess in (8, 13):
        found = []
        off = 0x600000
        while off < 0x800000:
            # 检查 stride_guess*40 范围内是否每 stride 处都是 FF 结尾
            okc = 0
            for k in range(40):
                p = off + k * stride_guess
                if p < len(a) and a[p:p + 1] and a[min(p + stride_guess - 1, len(a) - 1)] == 0xFF:
                    okc += 1
            if okc >= 36:
                found.append(off)
                off += stride_guess * 40
            else:
                off += stride_guess
        print(f"  stride={stride_guess}: 候选 {len(found)} 处"
              + ("  " + ", ".join(f"0x{o:06X}" for o in found[:8]) if found else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
