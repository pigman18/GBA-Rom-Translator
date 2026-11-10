#!/usr/bin/env python3
"""关键排查：SLT2 里的中文码位是否超出字库范围。

SLT2 里宝可梦名存的中文码位：
  巨沼怪    0x078e 0x1046 0x049e
  蜥蜴王    0x1c58 0x1c5d 0x0d5d
  沙基拉斯  0x0b91 0x0586 0x0822 0x0c5c
  蘑蘑菇    0x0998 0x0998 0x0485

对比：
  CHS_FONT_GLYPH_MAX = 7168 = 0x1C00
  这些码位里 0x1c58 / 0x1c5d 已经**超过 0x1C00**！
  ⇒ 超出字库范围 → 画不出 → 显示成别的字（如「蛋」）

这正是「蛋」bug 的根因。

但为什么是「蛋」而不是空白？因为 pack_glyph_index 的映射关系：
  gidx = ((idx) << 8) | trail，其中 idx 由 lead 计算
  若 gidx 越界，可能落回某个固定字形。

用法：
    python scripts/research/ruby/a2_check_glyph_range.py
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
OUT = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
SLOT = 0x01EA0000
CHS_MAX = 0x1C00        # CHS_FONT_GLYPH_MAX = 7168


def lead_trail_ok(lead: int, trail: int) -> bool:
    if lead >= 0xFA or trail >= 0xFA:
        return False
    if lead < 0x01 or lead > 0x1E:
        return False
    if lead in (0x06, 0x1B):
        return False
    return True


def pack_glyph_index(lead: int, trail: int) -> int:
    idx = lead
    if idx >= 6:
        if idx >= 0x1B:
            idx -= 1
        idx -= 1
    idx -= 1
    return ((idx << 8) | trail) & 0xFFFF


def main() -> int:
    rom = OUT.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    print(f"CHS_FONT_GLYPH_MAX = {CHS_MAX} = 0x{CHS_MAX:04X}\n")

    # 收集所有模块的 target_hex 里的 F9 00 码位
    print("=== 全库 F9 00 码位的 gidx 越界检查 ===")
    bad_total = 0
    checked_total = 0
    by_module = {}

    for e in d.get("entries") or []:
        th = (e.get("target_hex") or "").replace(" ", "")
        if not th:
            continue
        try:
            raw = bytes.fromhex(th)
        except ValueError:
            continue
        mod = e.get("module") or ""
        i = 0
        while i + 3 <= len(raw):
            if raw[i] == 0xF9 and raw[i + 1] == 0x00:
                lead, trail = raw[i + 2], raw[i + 3]
                checked_total += 1
                if lead_trail_ok(lead, trail):
                    gidx = pack_glyph_index(lead, trail)
                    if gidx >= CHS_MAX:
                        bad_total += 1
                        by_module[mod] = by_module.get(mod, 0) + 1
                        if by_module[mod] <= 3:
                            print(f"  ❌ {mod} {e.get('address')} "
                                  f"lead=0x{lead:02X} trail=0x{trail:02X} "
                                  f"gidx=0x{gidx:04X} (>0x{CHS_MAX:04X})")
                i += 4
            else:
                i += 1

    print()
    print(f"  检查 {checked_total:,} 个码位，越界 {bad_total:,} "
          f"({bad_total / max(checked_total, 1):.1%})")
    if by_module:
        print("  按模块:")
        for m, c in sorted(by_module.items(), key=lambda kv: -kv[1]):
            print(f"    {m:<18} {c}")

    # 查 lead 允许范围
    print()
    print("=== lead 的合法范围（text_translter.c lead_trail_ok）===")
    print("  lead ∈ [0x01, 0x1E]，排除 0x06 和 0x1B")
    print("  ⇒ 有效 lead 共 28 个")
    print(f"  ⇒ gidx 上限 = (27 << 8) | 0xFF = 0x{((27 << 8) | 0xFF):04X} = "
          f"{((27 << 8) | 0xFF)}")
    print(f"  CHS_FONT_GLYPH_MAX = {CHS_MAX} = 0x{CHS_MAX:04X}")
    print()
    print("  ⚠️ 关键矛盾：")
    print(f"    lead 全范围可达 gidx 0x1BFF = {(27 << 8) | 0xFF}，" )
    print(f"    但 CHS_MAX = {CHS_MAX} = 0x{CHS_MAX:04X}")
    print(f"    ⇒ gidx 在 [0x{CHS_MAX:04X}, 0x1BFF] 的字符会被判断越界、不画！")

    # 统计有多少字的 gidx 在这个区间
    print()
    print("=== 落在 [0x1C00, 0x1BFF] 无效区的字 ===")
    dead = 0
    for e in d.get("entries") or []:
        th = (e.get("target_hex") or "").replace(" ", "")
        try:
            raw = bytes.fromhex(th)
        except ValueError:
            continue
        i = 0
        while i + 3 <= len(raw):
            if raw[i] == 0xF9 and raw[i + 1] == 0x00:
                lead, trail = raw[i + 2], raw[i + 3]
                if lead_trail_ok(lead, trail):
                    gidx = pack_glyph_index(lead, trail)
                    if CHS_MAX <= gidx <= 0x1BFF:
                        dead += 1
                i += 4
            else:
                i += 1
    print(f"  共 {dead} 个码位落在此无效区")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
