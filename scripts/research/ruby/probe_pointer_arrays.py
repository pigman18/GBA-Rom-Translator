#!/usr/bin/env python3
"""找 ruby ROM 里的「指针数组」——元素是表内地址、间距规整的 u32 序列。

上一支脚本发现：
  属性名 0x1CBB0C.. 的元素地址出现在 0x388454/0x38845C/0x388464/...，
  间距正好 8 字节 → 这是一张指针数组（IndexTable）。

招式名/特性名 没有单个「基址字面量」，极可能也是靠同样的指针数组访问。
火红那边（FIRERED_FULL_LOGIC §2.3）10/68 等长块就是这种情况：元素各自有指针。

本脚本：对每张目标表，扫描「连续 ≥N 个 u32 都指向该表范围内」的序列。

用法：
    python scripts/research/ruby/probe_pointer_arrays.py
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
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"

GBA_BASE = 0x08000000
MIN_RUN = 8  # 至少 8 个连续指针才算数组

TARGETS = ["招式名", "特性名", "属性名", "道具名", "图鉴分类名", "秘密基地装饰名", "树果名", "性格名", "宝可梦名"]


def parse_hex(s) -> int:
    return int(str(s).replace("0x", "").replace("0X", ""), 16)


def find_pointer_runs(rom: bytes, lo: int, hi: int, min_run: int = MIN_RUN):
    """扫全 ROM 4 字节对齐位置，找「值落在 [lo,hi) 且连续」的指针串。"""
    runs = []
    cur_start = None
    cur_len = 0
    n = len(rom) - 4
    for off in range(0, n, 4):
        v = struct.unpack_from("<I", rom, off)[0] - GBA_BASE
        inside = lo <= v < hi
        if inside:
            if cur_start is None:
                cur_start = off
                cur_len = 0
            cur_len += 1
        else:
            if cur_start is not None and cur_len >= min_run:
                runs.append((cur_start, cur_len))
            cur_start = None
            cur_len = 0
    if cur_start is not None and cur_len >= min_run:
        runs.append((cur_start, cur_len))
    return runs


def main() -> int:
    rom = ROM.read_bytes()
    mods = (json.loads(TEXTS.read_text(encoding="utf-8")).get("modules") or {})
    print(f"ROM {len(rom):,} B\n")

    summary = []
    for name in TARGETS:
        meta = mods.get(name)
        if not meta:
            continue
        start = parse_hex(meta["start"])
        end = parse_hex(meta["end"])
        runs = find_pointer_runs(rom, start, end)

        print(f"=== {name} ===  表范围 0x{start:06X}..0x{end:06X}")
        if not runs:
            print(f"  ❌ 无 ≥{MIN_RUN} 连续指针串")
            summary.append((name, 0, 0))
        else:
            total = sum(r[1] for r in runs)
            print(f"  找到 {len(runs)} 条连续指针串，共 {total} 个指针")
            for off, length in runs[:6]:
                print(f"     数组 @ 0x{off:06X}  长度 {length}")
            if len(runs) > 6:
                print(f"     … 另 {len(runs)-6} 条")
            summary.append((name, len(runs), total))
        print()

    print("=== 汇总 ===")
    for name, nruns, total in summary:
        flag = "✅ 有指针数组" if total >= 8 else "❌ 未发现"
        print(f"  {name:<14} 串数 {nruns:>3}  指针 {total:>4}  {flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
