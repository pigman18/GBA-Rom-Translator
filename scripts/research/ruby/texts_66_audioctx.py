#!/usr/bin/env python3
"""texts_66: C 类音效标签到底上不上屏 —— 用指针溯源定位使用者。

texts_65 显示 17/17 都有指针。但「有指针」不等于「上屏」——也可能是资源名查表。
关键：看这些指针装在哪种结构里。

方法：
  1. 打印每条指向它的指针所在位置
  2. 看那些位置是不是「连续 u16 索引表 / 资源名表」的形态
  3. 与已知「上屏文本」的指针形态对照

用法: python scripts/research/ruby/texts_66_audioctx.py
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BASE = 0x08000000


def to_int(v):
    if v is None:
        return None
    if isinstance(v, int):
        return v
    s = str(v).strip()
    try:
        return int(s, 16) if s.lower().startswith("0x") else int(s, 10)
    except ValueError:
        return None


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    sup = [e for e in d["entries"] if e.get("module") == "补漏剧情"]
    c_entries = [e for e in sup
                 if 0x3A5000 <= to_int(e["address"]) - BASE < 0x3A6000]

    # 指针索引
    ptrs = {}
    for o in range(0, len(rom) - 4, 4):
        v = struct.unpack_from("<I", rom, o)[0]
        if BASE <= v < BASE + len(rom):
            ptrs.setdefault(v - BASE, []).append(o)

    print("=" * 112)
    print("C 类音效标签：指向它们的指针在哪、周围是什么结构")
    print("=" * 112)
    for e in c_entries:
        off = to_int(e["address"]) - BASE
        refs = ptrs.get(off, [])
        print(f"\n  {e['original']!r}  @0x{off:06X}")
        for r in refs:
            ctx = rom[max(0, r - 16):r + 16].hex(" ")
            # 检查 r 是否落在连续指针数组里
            run = 1
            k = r - 4
            while k >= 0 and r - k < 0x80:
                v = struct.unpack_from("<I", rom, k)[0]
                if BASE <= v < BASE + len(rom):
                    run += 1
                    k -= 4
                else:
                    break
            k = r + 4
            while k + 4 <= len(rom) and k - r < 0x80:
                v = struct.unpack_from("<I", rom, k)[0]
                if BASE <= v < BASE + len(rom):
                    run += 1
                    k += 4
                else:
                    break
            print(f"    指针在 0x{r:06X}（所在连续指针串长度 ~{run}）")
            print(f"      上下文: {ctx}")

    print()
    print("=" * 112)
    print("对照：一个已知上屏文本（战斗台词）的指针形态")
    print("=" * 112)
    sample = 0x3DA6E5  # \10の \17で\n\0Eは ねむってしまった！
    refs = ptrs.get(sample, [])
    print(f"  0x{sample:06X} 的指针: {[hex(x) for x in refs]}")
    for r in refs[:3]:
        ctx = rom[max(0, r - 16):r + 16].hex(" ")
        print(f"    0x{r:06X} 上下文: {ctx}")

    print()
    print("=" * 112)
    print("结论")
    print("=" * 112)
    print("""
  判定依据：
    · 若音效标签的指针成片落在「连续的字符串指针数组」里 → 是资源名表（不上屏）
    · 若指针零星、或指向的位置在脚本/UI 代码里 → 可能上屏

  具体见上面的「连续指针串长度」。长度大（几十）= 名表；长度 1-2 = 单点引用。
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
