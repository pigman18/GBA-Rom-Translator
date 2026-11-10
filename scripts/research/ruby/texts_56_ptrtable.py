#!/usr/bin/env python3
"""texts_56: 复查 0x3B3E64 指针表 + 我 P3 漏检的根因。

texts_55 的 P3 只检查了 4 个 base（0x3B2100/0x3B2800/0x3B3900/0x3B3A00）
各 0x200 范围 —— **0x3B3E64 完全不在覆盖范围内**，所以漏检。
这不是「判定逻辑错」，是「扫描窗口没覆盖」。

本脚本做全区间扫描：找所有「连续 3+ 个对齐 u32 都指向目标区间」的数组，
不预设位置。

用法: python scripts/research/ruby/texts_56_ptrtable.py
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
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BASE = 0x08000000

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import decode_pcs  # noqa: E402

TGT_LO, TGT_HI = 0x3B219B, 0x3B3900


def read_str(rom: bytes, off: int, limit: int = 64) -> str:
    for i in range(off, min(len(rom), off + limit)):
        if rom[i] == 0xFF:
            return decode_pcs(rom[off:i + 1])
    return ""


def main() -> int:
    rom = ROM_PATH.read_bytes()

    print("=" * 112)
    print("A. 验证 0x3B3E64 处的指针表")
    print("=" * 112)
    for base in (0x3B3E64,):
        print(f"\n  表基址 0x{base:06X}：")
        for k in range(24):
            o = base + k * 4
            v = struct.unpack_from("<I", rom, o)[0]
            if BASE <= v < BASE + len(rom):
                t = v - BASE
                s = read_str(rom, t)
                inzone = "★区间内" if TGT_LO <= t < TGT_HI else ""
                print(f"    [{k:>2}] 0x{o:06X}: 0x{v:08X} -> 0x{t:06X} "
                      f"{s!r} {inzone}")
            else:
                print(f"    [{k:>2}] 0x{o:06X}: 0x{v:08X}  <非指针/表尾>")
                if k > 0:
                    break

    print()
    print("=" * 112)
    print("B. 全 ROM 扫描：所有指向目标区间的连续数组（不预设位置）")
    print("=" * 112)
    runs = []
    k = 0
    n = len(rom)
    while k + 4 <= n:
        v = struct.unpack_from("<I", rom, k)[0]
        if BASE <= v < BASE + len(rom) and TGT_LO <= v - BASE < TGT_HI:
            start = k
            cnt = 0
            while k + 4 <= n:
                v2 = struct.unpack_from("<I", rom, k)[0]
                if BASE <= v2 < BASE + len(rom) and TGT_LO <= v2 - BASE < TGT_HI:
                    cnt += 1
                    k += 4
                else:
                    break
            if cnt >= 2:
                runs.append((start, cnt))
        else:
            k += 4

    print(f"  找到 {len(runs)} 段连续数组（len>=2）")
    for start, cnt in sorted(runs, key=lambda x: -x[1]):
        print(f"    0x{start:06X}  长度 {cnt} 项  "
              f"跨度 0x{start:06X}..0x{start + cnt*4 - 1:06X}")

    print()
    print("=" * 112)
    print("C. 我 P3 漏检的根因")
    print("=" * 112)
    print("  texts_55 的 P3 只检查了 4 个窗口：")
    for base in (0x3B2100, 0x3B2800, 0x3B3900, 0x3B3A00):
        print(f"    0x{base:06X} .. 0x{base+0x1FF:06X}")
    print(f"  0x3B3E64 落在 0x3B3A00..0x3B3C00 之后 → **未被任何窗口覆盖**")
    print("  → 漏检原因是「扫描窗口没覆盖」，不是判定逻辑错。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
