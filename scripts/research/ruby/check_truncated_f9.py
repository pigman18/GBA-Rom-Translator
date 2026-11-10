#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查表格里被切断的 F9 字形序列。

## 为什么需要

F9 00 hi lo 是 4 字节一组。若名字区填充按
    body + FF * (usable - len(body))
且 len(body) 不是 4 的倍数，最后一组 F9 就会被 FF 顶掉一半，
运行时读成 `f9 00 ff` → 画出错误字形 / 乱码。

本脚本扫描指定表的新数据，找出所有「F9 序列不完整」的项。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ASM = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook" / "gen" / "table_data.asm"
OUT = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"

SPECS = [
    ("TblMoveNames",       354, 32,  0, 32),
    ("TblSpeciesCategory", 386, 28,  6,  6),
    ("TblItemNames",       348, 48,  0, 17),
    ("TblDecorNames",      120, 28, 13, 10),
    ("TblAbilityNames",     77, 32,  0, 32),
    ("TblTypeNames",        18, 20,  0, 20),
    ("TblSpeciesNames",    412, 24,  0, 24),
    ("TblAbilityDesc",      78, 48,  0, 48),
    ("TblBerryNames",       43, 28,  0, 10),
]


def table_addrs() -> dict[str, int]:
    src = ASM.read_text(encoding="utf-8")
    return {m.group(2): int(m.group(1), 16)
            for m in re.finditer(
                r"\.org\s+(0x[0-9A-Fa-f]+)\s*\n\.align\s+4\s*\n(\w+):", src)}


def main() -> int:
    addrs = table_addrs()
    rom = OUT.read_bytes()
    total_bad = 0

    for sym, n, stride, noff, usable in SPECS:
        gba = addrs.get(sym)
        if gba is None:
            print(f"[warn] {sym} 不在 table_data.asm")
            continue
        base = gba - 0x08000000
        bad: list[tuple[int, str]] = []
        for i in range(n):
            off = base + i * stride + noff
            seg = rom[off:off + usable]
            j = seg.find(b"\xFF")
            body = seg[:j] if j >= 0 else seg
            if b"\xF9" not in body:
                continue
            # 逐组检查 F9 00 hi lo
            k = 0
            while k < len(body):
                if body[k] == 0xF9:
                    if k + 4 > len(body) or body[k + 1] != 0x00:
                        bad.append((i, body[k:k + 4].hex(" ")))
                        break
                    k += 4
                else:
                    k += 1
        if bad:
            print(f"{sym}: {len(bad)} 项 F9 序列被切断")
            for i, b in bad[:5]:
                print(f"   entry[{i}] {b}")
            total_bad += len(bad)
        else:
            print(f"{sym}: OK")

    print()
    print(f"合计被切断 {total_bad} 项" if total_bad else "全部完整")
    return 0 if not total_bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
