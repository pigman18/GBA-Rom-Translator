#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定位结构体表里名字字段的**真实**偏移（不采信配置）。

配置里的 name_offset / usable 是人工候选值，可能与 ROM 实际不符
（道具名就出过这种事：+0x10 被当成名字指针，实测是说明文本指针）。

本脚本对每个 entry 逐字节找「像日文 PCS 字符串」的连续段
（假名范围 + FF 终止），统计出现最多的起始偏移 = 真名字偏移。
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
sys.path.insert(0, str(ROOT / "src"))
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

TABLES = {
    "图鉴分类名": dict(base=0x384746, stride=28, n=386),
    "秘密基地装饰名": dict(base=0x3C2A44, stride=28, n=120),
    "树果名": dict(base=0x3A1034, stride=28, n=43),
    "道具名": dict(base=0x39A648, stride=40, n=348),
}

# 日文 PCS：0x01..0x1E 左右是假名/汉字，0x50..0x9F 也是
KANA = set(range(0x01, 0x20)) | set(range(0x50, 0xA0))


def main() -> int:
    from meowth.jp_pcs import decode_pcs

    if len(sys.argv) < 2 or sys.argv[1] not in TABLES:
        print(__doc__)
        print("可用：" + ", ".join(TABLES))
        return 3
    name = sys.argv[1]
    cfg = TABLES[name]
    base, stride, n = cfg["base"], cfg["stride"], cfg["n"]
    rom = ROM.read_bytes()

    print(f"=== {name} base=0x{base:06X} stride={stride} n={n}\n")

    starts: Counter = Counter()
    lens: dict[int, list[int]] = {}

    for i in range(n):
        e = base + i * stride
        b = rom[e:e + stride]
        # 找所有「连续 >=2 个假名字节 + 后续出现 FF」的起点
        j = 0
        while j < stride - 1:
            if b[j] in KANA:
                k = j
                while k < stride and b[k] in KANA:
                    k += 1
                run = k - j
                # 结束处应是 FF 或非假名
                if run >= 2 and k < stride and b[k] == 0xFF:
                    starts[j] += 1
                    lens.setdefault(j, []).append(run)
                j = max(k, j + 1)
            else:
                j += 1

    if not starts:
        print("未找到 PCS 字符串段")
        return 1

    print("按「起始偏移」统计命中 entry 数：")
    for off, cnt in starts.most_common(8):
        ls = sorted(lens.get(off, []))
        med = ls[len(ls) // 2] if ls else 0
        print(f"  +0x{off:02X}: {cnt:4d}/{n} 项   长度中位 {med}  最长 {ls[-1] if ls else 0}")

    best = starts.most_common(1)[0][0]
    print(f"\n★ 真实名字偏移 = +0x{best:02X}")
    print(f"   样例解码：")
    for i in range(min(3, n)):
        e = base + i * stride + best
        s = rom[e:e + 30]
        j = s.find(b"\xff")
        txt = decode_pcs(s[:j + 1]) if j >= 0 else "?"
        print(f"     entry[{i}] = {txt!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
