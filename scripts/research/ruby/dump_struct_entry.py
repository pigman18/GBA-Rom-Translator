#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打印某张结构体表的 entry 原始布局（逐字节 + 名字解码）。"""
from __future__ import annotations

import sys
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
    "图鉴分类名": dict(base=0x384746, stride=28, n=386, noff=6, usable=6),
    "秘密基地装饰名": dict(base=0x3C2A44, stride=28, n=120, noff=13, usable=10),
    "树果名": dict(base=0x3A1034, stride=28, n=43, noff=0, usable=10),
}


def main() -> int:
    from meowth.jp_pcs import decode_pcs

    if len(sys.argv) < 2 or sys.argv[1] not in TABLES:
        print(__doc__)
        print("可用：" + ", ".join(TABLES))
        return 3
    name = sys.argv[1]
    cfg = TABLES[name]
    base, stride, n = cfg["base"], cfg["stride"], cfg["n"]
    noff, usable = cfg["noff"], cfg["usable"]

    rom = ROM.read_bytes()
    print(f"=== {name}  base=0x{base:06X} stride={stride} "
          f"name@+{noff} usable={usable}\n")
    for i in (0, 1, 2, n // 2):
        e = base + i * stride
        print(f"entry[{i}] @0x{e:06X}")
        for k in range(0, stride, 7):
            seg = rom[e + k:e + min(k + 7, stride)]
            mark = "  <-名字" if noff <= k < noff + usable else ""
            print(f"  +{k:02X}: {seg.hex(' ')}{mark}")
        s = rom[e + noff:e + noff + usable]
        j = s.find(b"\xff")
        txt = decode_pcs(s[:j + 1]) if j >= 0 else "?"
        print(f"  name = {txt!r}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
