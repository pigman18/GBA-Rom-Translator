#!/usr/bin/env python3
"""道具名结构最后一问：名字在 40B 头内，还是独立数组？

已知铁证：
  代码：base + idx*40  （反汇编 0x0A5388..0x0A5390）
  build.json 名字地址 = 0x39A648 + i*40 + 0x28

若名字在「40B 头内」，则 name@+0x28 意味着名字只能用 40-0x28 = 0 字节 —— 不可能。
所以必然有第二种解释。

解释 X：代码算的是 `base + idx*40`，但 base 是 0x39A648，
        而**每项 40B 里，前 0x28 是头、后 0x18=24B 是名字**？
        40 - 0x28 = 0x18 = 24 字节。但我说算出 0 是因为 0x28 十六进制 = 40 十进制。

⚠️ 我的错误：0x28 = 40（十进制），不是 0x28 字节 = 28 字节！
   名字偏移就是 0x28 = 40 字节 = 整个项的大小。
   所以 name@+0x28 表示「名字在下一项的起点」。

正确解读：
  item[i] 的 40 字节全是「头」
  item[i] 的名字在 base + (i+1)*40 = base + i*40 + 40

验证：0x39A648 + 0*40 + 40 = 0x39A670 ✅ 与实测第一名字地址吻合。

⇒ 结构 = [头0][头1][头2]...[头N][名0][名1]...[名N]？
  还是 [头0][名0紧随其后但算作头1]？

必须用字节判定。用法：
    python scripts/research/ruby/a2_item_layout.py
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
BASE = 0x39A648
STRIDE = 40


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    addrs = []
    for e in d.get("entries") or []:
        if e.get("module") != "道具名":
            continue
        try:
            a = int(str(e.get("address") or "").replace("0x", ""), 16)
        except ValueError:
            continue
        if a >= GBA_BASE:
            a -= GBA_BASE
        addrs.append(a)
    addrs.sort()

    print(f"名字地址 {len(addrs)} 条，范围 0x{addrs[0]:06X}..0x{addrs[-1]:06X}")
    print()

    # 关键：名字地址 = BASE + i*40 + 40 ?
    print("=== 检验：名字地址 == BASE + (i+1)*40 ===")
    ok = 0
    for i, a in enumerate(addrs[:10]):
        expect = BASE + (i + 1) * STRIDE
        mark = "✅" if a == expect else "❌"
        print(f"  i={i} 实际 0x{a:06X}  预期 0x{expect:06X}  {mark}")
        if a == expect:
            ok += 1
    print(f"  前 10 个吻合 {ok}/10")
    print()

    # 那第 349 项之后是什么？
    last = addrs[-1]
    print(f"=== 最后一个名字 0x{last:06X} ===")
    print(f"  后面 64B: {rom[last:last + 64].hex(' ')}")
    print()

    # 若名字就是「每项的后 40 字节」，那前 40B 是什么
    print("=== 结构再解读 ===")
    print("  若 name[i] = BASE + (i+1)*40，则 BASE + i*40 处的 40 字节是")
    print("  「item i-1 的名字之后」到「item i 的名字之前」的空间。")
    print()
    for i in range(3):
        head = rom[BASE + i * STRIDE: BASE + (i + 1) * STRIDE]
        name = rom[BASE + (i + 1) * STRIDE: BASE + (i + 1) * STRIDE + 16]
        print(f"  [0x{BASE + i*STRIDE:06X}..+40) {head.hex(' ')}")
        print(f"    名字@{0x39A648 + (i+1)*STRIDE:06X}: {name.hex(' ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
