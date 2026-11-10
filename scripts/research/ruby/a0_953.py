#!/usr/bin/env python3
"""A0.2：953 条「无 ldr 引用」的指针站点是什么形态？

已知：
  150 条被 ldr 确认（代码字面量池，真指针）
  953 条无 ldr 引用，站点多在 0x3A69F8 这类表区

待查：953 条是不是「脚本文本指针表」或「结构体字段」。
判据：
  A. 站点连续等距（4/8 字节）→ 指针数组
  B. 站点前有 opcode（02/03/04）→ 脚本内嵌
  C. 孤立 → 存疑

用法：
    python scripts/research/ruby/a0_953.py
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
sys.path.insert(0, str(ROOT / "src"))

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
GBA_BASE = 0x08000000


def find_ldr(rom: bytes, lit: int, back: int = 4096) -> bool:
    for off in range(max(0, lit - back), lit, 2):
        hw = struct.unpack_from("<H", rom, off)[0]
        if (hw & 0xF800) != 0x4800:
            continue
        imm = (hw & 0xFF) * 4
        if ((off + 4) & ~3) + imm == lit:
            return True
    return False


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))
    entries = d.get("entries") or []

    from meowth.policy import collect_entry_text_spans, ptr_site_in_text_body
    text_spans = collect_entry_text_spans(entries)

    f980 = [e for e in entries
            if e.get("type") == "replace" and e.get("phrase_code") is not None
            and (e.get("module") or "") == "剧情"]

    idx: dict[int, list[int]] = {}
    for off in range(0, len(rom) - 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            idx.setdefault(v - GBA_BASE, []).append(off)

    # 收集无 ldr 的站点
    sites_no_ldr = []
    for e in f980:
        a = e.get("address") or "0x0"
        try:
            addr = int(str(a).replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        for s in (idx.get(addr) or []):
            if s & 3:
                continue
            if ptr_site_in_text_body(s, text_spans):
                continue
            if not find_ldr(rom, s):
                sites_no_ldr.append((s, addr, e))
                break

    print(f"无 ldr 引用的站点: {len(sites_no_ldr):,}\n")

    # 站点是否成组（前后也是指针）
    group_stats: Counter = Counter()
    for s, addr, e in sites_no_ldr:
        prev_is_ptr = False
        next_is_ptr = False
        if s >= 4:
            v = struct.unpack_from("<I", rom, s - 4)[0]
            prev_is_ptr = GBA_BASE <= v < 0x0A000000
        if s + 8 <= len(rom):
            v = struct.unpack_from("<I", rom, s + 4)[0]
            next_is_ptr = GBA_BASE <= v < 0x0A000000
        if prev_is_ptr and next_is_ptr:
            group_stats["前后都是指针（指针数组）"] += 1
        elif prev_is_ptr:
            group_stats["前面是指针"] += 1
        elif next_is_ptr:
            group_stats["后面是指针"] += 1
        else:
            group_stats["孤立"] += 1

    print("=== 站点成组情况 ===")
    for k, v in group_stats.most_common():
        print(f"  {k:<26} {v:>5}")
    print()

    print("=== 样本（前 12）===")
    for s, addr, e in sites_no_ldr[:12]:
        ctx = []
        for k in range(-2, 3):
            p = s + k * 4
            if 0 <= p < len(rom) - 4:
                v = struct.unpack_from("<I", rom, p)[0]
                t = v - GBA_BASE if GBA_BASE <= v < 0x0A000000 else None
                ctx.append(f"{k:+d}:0x{t:06X}" if t else f"{k:+d}:0x{v:08X}")
        print(f"  站点 0x{s:06X} → 文本 0x{addr:06X}")
        print(f"    邻域: {' '.join(ctx)}")
        print(f"    原文: {(e.get('original') or '')[:40]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
