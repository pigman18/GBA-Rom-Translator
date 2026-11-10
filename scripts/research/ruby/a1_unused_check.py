#!/usr/bin/env python3
"""A1.4 定案：919 条零引用文本，用「压缩流」假设检验。

已知 u16 偏移假设不成立（最高 16.6%）。

0x3B27D0 的 u16 序列：
  389 64 361 26 338 285 337 407 408 325 45 392 171 388 348 350 ...
这些值域 0-410，像「索引/编号」而不是「偏移」。

剩下可能：
  A. 这些文本被 LZ77/LZ78 压缩包引用（压缩后指针不可见）
  B. 被「文本长度表 + 累积和」访问（如 pokeruby 的 custom_text）
  C. 根本不参与显示（是未使用数据 / 开发残留）

关键判据：若这些文本在游戏里**不显示**，它们就是无效数据，
应该从 texts.json 里**删掉**（用户提到「大量无效文本」）。

验证思路：
  - 检查这些文本是否在 pokeruby 已知的「未使用文本」区
  - 检查 0x3B2810 附近的文本（こうかん / サファイア / せいかく）
    是否是「术语表」——这类通常在菜单/帮助里显示

用法：
    python scripts/research/ruby/a1_unused_check.py
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
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
OWN = ROOT / "work" / "_probe" / "a1_ownership.json"
GBA_BASE = 0x08000000


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    by_addr = {}
    for e in d.get("entries") or []:
        a = e.get("address") or ""
        try:
            addr = int(str(a).replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        by_addr[addr] = e

    own = json.loads(OWN.read_text(encoding="utf-8"))
    targets = {int(r["addr"].replace("0x", ""), 16) for r in (own.get("NO_PTR") or [])}

    ref_targets: set[int] = set()
    for off in range(0, len(rom) - 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            ref_targets.add(v - GBA_BASE)

    zero = sorted(t for t in targets if t not in ref_targets and t > 0 and rom[t-1] == 0xFF)
    print(f"零引用独立串: {len(zero):,}\n")

    # 内容分类
    print("=== 这些文本的内容特征 ===")
    short = mid = long_ = 0
    contents = []
    for a in zero:
        e = by_addr.get(a)
        if not e:
            continue
        orig = e.get("original") or ""
        n = len(orig)
        if n <= 6:
            short += 1
        elif n <= 30:
            mid += 1
        else:
            long_ += 1
        if len(contents) < 40:
            contents.append(orig)
    print(f"  短(<7字): {short}   中(7-30): {mid}   长(>30): {long_}")
    print()
    print("=== 前 40 条内容 ===")
    for c in contents:
        print(f"  {c!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
