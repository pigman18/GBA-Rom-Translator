#!/usr/bin/env python3
"""A2.4 验证：用 table_expand + table_relink 对「道具名」做扩表演练。

道具名是最安全的一档：entry_size=40、名称字段在 @0x18、字段宽 24B，
中文 2 字（F9 00 hi lo ×2 + FF = 9B）塞得下 → 可以「保持 stride，只改字面量」。

本脚本**不写 ROM**，只做：
  1. 用真实译文构造新表
  2. 走 expand_fixed（保持 stride）
  3. 找指针字面量站点（验证 relink 可行）
  4. 报告将要 patch 的位置

用法：
    python scripts/research/ruby/a2_item_names_dryrun.py
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
sys.path.insert(0, str(ROOT / "src"))

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"

# 道具名表几何（实测）
ENTRY_SIZE = 40
NAME_OFF = 0x18
NAME_CAP = 24        # 名称字段可用宽度（40 - 0x18 = 24，实际含边界）
TABLE_BASE = 0x39A648
N_ITEMS = 348


def main() -> int:
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path
    from meowth.table_expand import (
        ExpandAllocator, expand_fixed, encode_body, describe,
    )
    from meowth.table_relink import find_literal_sites, find_ldr_literals

    cm = Charmap(charmap_path=get_charmap_path("POKEMON_RUBY_AXVJ00"),
                 target_lang="zh-Hans")
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    # 取道具名的 F980 条目
    items = {}
    for e in d.get("entries") or []:
        if e.get("module") != "道具名":
            continue
        a = e.get("address") or ""
        try:
            addr = int(str(a).replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= 0x08000000:
            addr -= 0x08000000
        items[addr] = e

    print(f"道具名条目: {len(items):,}\n")

    # 构造全表 bodies（用译文；没有译文的保留原文）
    bodies: list[bytes] = []
    too_long = 0
    for i in range(N_ITEMS):
        off = TABLE_BASE + i * ENTRY_SIZE + NAME_OFF
        e = items.get(off)
        text = (e.get("translated") or "") if e else ""
        if text:
            body = encode_body(cm, text)
        else:
            # 无译文：保留原字节（截到 FF）
            raw = rom[off:off + ENTRY_SIZE]
            ff = raw.find(b"\xFF")
            body = raw[:ff + 1] if ff >= 0 else raw[:NAME_CAP]
        if len(body) > NAME_CAP:
            too_long += 1
            if too_long <= 5:
                print(f"  ⚠️ item{i} @0x{off:06X}: {len(body)}B > {NAME_CAP}B  {text!r}")
        bodies.append(body)

    print(f"  超长项: {too_long:,} / {N_ITEMS:,}")
    print()

    # 走 expand_fixed（会因超长报错，先只统计）
    alloc = ExpandAllocator(start=0x09F00000, size=0x100000)
    ok = 0
    for b in bodies:
        if len(b) <= NAME_CAP:
            ok += 1
    print(f"=== 能保持 stride 的项: {ok:,} / {N_ITEMS:,} "
          f"({ok/N_ITEMS:.1%}) ===")
    print()

    if too_long == 0:
        plan = expand_fixed(
            name="道具名", orig_base=TABLE_BASE,
            stride=ENTRY_SIZE, n=N_ITEMS, bodies=bodies, alloc=alloc,
            name_offset=NAME_OFF,
        )
        print("=== expand_fixed 成功 ===")
        print(f"  {describe(plan)}")
        print(f"  blob 大小 {len(plan.blob):,} B")
    else:
        print("=== 有超长项，需改用 expand_varlen ===")
        print("  先用 expand_varlen 演练（不受 stride 限制）：")
        from meowth.table_expand import expand_varlen
        alloc2 = ExpandAllocator(start=0x09F00000, size=0x100000)
        plan = expand_varlen(
            name="道具名", orig_base=TABLE_BASE,
            orig_stride=ENTRY_SIZE, n=N_ITEMS, bodies=bodies, alloc=alloc2,
            name_offset=NAME_OFF,
        )
        print(f"  {describe(plan)}")
        print(f"  串区+指针数组 {len(plan.blob):,} B")

    # relink 预检（用表基址，不是名称字段！）
    print()
    print("=== relink 预检：**表基址** 的字面量站点 ===")
    old_gba = 0x08000000 + TABLE_BASE
    sites = find_literal_sites(rom, old_gba, require_aligned=True)
    print(f"  值为 0x{old_gba:08X} 的 4 对齐字面量: {len(sites)} 处")
    ldr_n = sum(1 for s in sites if find_ldr_literals(rom, s))
    print(f"  其中被 ldr [pc] 引用: {ldr_n} 处")
    for s in sites[:6]:
        ldrs = find_ldr_literals(rom, s)
        print(f"    0x{s:06X}" + (f"  ← ldr 0x{ldrs[0]:X}" if ldrs else "  (无 ldr)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
