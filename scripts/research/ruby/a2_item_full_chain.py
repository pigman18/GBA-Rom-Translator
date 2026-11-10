#!/usr/bin/env python3
"""A2.4 全链路验证：扩表 → 排列 → relink，产出可应用的 patch 列表。

对「道具名」跑完整三段式：
  1. 用真实译文 expand_varlen（348 项，变长）
  2. 分配扩展区地址
  3. relink：把 14 处指向旧表的字面量改成新指针数组地址
  4. 输出 patch 列表（**不写 ROM**）

验证点：
  - 指针数组里每项都指向正确的串
  - 所有 14 处字面量都能被安全改写
  - 新表不越界、不与已占用区重叠

用法：
    python scripts/research/ruby/a2_item_full_chain.py
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
sys.path.insert(0, str(ROOT / "src"))

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
OUT = ROOT / "work" / "_probe" / "a2_item_patches.json"

# 道具名表（实测）
TABLE_BASE = 0x39A648
ENTRY_SIZE = 40
NAME_OFF = 0x28
N_ITEMS = 348
GBA_BASE = 0x08000000

# 扩展区：从 0x09F00000 起（高于所有已知占用）
ALLOC_START = 0x09F00000
ALLOC_SIZE = 0x100000


def main() -> int:
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path
    from meowth.table_expand import (ExpandAllocator, expand_varlen,
                                     encode_body, describe)
    from meowth.table_relink import find_literal_sites, find_ldr_literals, Patch

    cm = Charmap(charmap_path=get_charmap_path("POKEMON_RUBY_AXVJ00"),
                 target_lang="zh-Hans")
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    items = {}
    for e in d.get("entries") or []:
        if e.get("module") != "道具名":
            continue
        try:
            addr = int(str(e.get("address") or "").replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        items[addr] = e

    # ---- 阶段 1：构造 bodies ----
    bodies: list[bytes] = []
    n_translated = 0
    for i in range(N_ITEMS):
        off = TABLE_BASE + i * ENTRY_SIZE + NAME_OFF
        e = items.get(off)
        text = (e.get("translated") or "") if e else ""
        if text:
            body = encode_body(cm, text)
            n_translated += 1
        else:
            raw = rom[off:off + ENTRY_SIZE]
            ff = raw.find(b"\xFF")
            body = raw[:ff + 1] if ff >= 0 else raw[:1] + b"\xFF"
        bodies.append(body)

    print(f"=== 阶段 1：构造 {N_ITEMS} 项（其中 {n_translated} 项有译文）===")
    total_body = sum(len(b) for b in bodies)
    print(f"  串区总字节 {total_body:,}")

    # ---- 阶段 2：扩表 + 排列 ----
    alloc = ExpandAllocator(start=ALLOC_START, size=ALLOC_SIZE)
    plan = expand_varlen(
        name="道具名", orig_base=TABLE_BASE, orig_stride=ENTRY_SIZE,
        n=N_ITEMS, bodies=bodies, alloc=alloc, name_offset=NAME_OFF,
    )
    print()
    print("=== 阶段 2：新区排列 ===")
    print(f"  {describe(plan)}")
    print(f"  串区 {plan.ptrarr_off:,} B + 指针数组 {4 * N_ITEMS:,} B "
          f"= {len(plan.blob):,} B")
    print(f"  新区范围 0x{plan.new_base:06X}..0x{plan.new_base + len(plan.blob):06X}")

    # 验证指针数组正确性
    bad = 0
    for i in range(N_ITEMS):
        ptr = struct.unpack_from("<I", plan.blob, plan.ptrarr_off + i * 4)[0]
        expect = GBA_BASE + plan.new_base + plan.item_offsets[i]
        if ptr != expect:
            bad += 1
            if bad <= 3:
                print(f"  ❌ ptr[{i}] = 0x{ptr:08X} != 0x{expect:08X}")
    print(f"  指针数组校验: {N_ITEMS - bad}/{N_ITEMS} 正确"
          + ("  ✅" if bad == 0 else f"  ❌ {bad} 错"))

    # 验证每项串以 FF 结尾
    bad_ff = sum(1 for i in range(N_ITEMS)
                 if plan.blob[plan.item_offsets[i] +
                              (len(bodies[i]) - 1)] != 0xFF)
    print(f"  串结尾 FF 校验: {'全部正确 ✅' if bad_ff == 0 else f'{bad_ff} 项异常 ❌'}")

    # ---- 阶段 3：relink ----
    print()
    print("=== 阶段 3：指针修改 ===")
    old_gba = GBA_BASE + TABLE_BASE
    sites = find_literal_sites(rom, old_gba, require_aligned=True)
    print(f"  旧表基址 0x{old_gba:08X} 的字面量: {len(sites)} 处")

    patches: list[Patch] = []
    new_gba = plan.ptrarr_gba
    for s in sites:
        cur = struct.unpack_from("<I", rom, s)[0]
        if cur != old_gba:
            continue
        ldrs = find_ldr_literals(rom, s)
        patches.append(Patch(
            s, struct.pack("<I", new_gba),
            f"literal→pointer_array (ldr@0x{ldrs[0]:X})" if ldrs
            else "literal→pointer_array (裸指针)",
        ))

    print(f"  生成 patch {len(patches)} 条")
    for p in patches[:6]:
        print(f"    0x{p.offset:06X}: {p.data.hex(' ')}  {p.label}")

    # ---- 汇总 ----
    print()
    print("=== 全链路结果 ===")
    print(f"  阶段1+2: {len(plan.blob):,} B 新表 @0x{plan.new_base:06X}")
    print(f"  阶段3:   {len(patches)} 处字面量改写")
    print(f"  预计消灭 F980: {n_translated} 条")

    # 保存
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "table": "道具名",
        "orig_base": f"0x{TABLE_BASE:06X}",
        "new_base": f"0x{plan.new_base:06X}",
        "ptrarr": f"0x{plan.ptrarr_gba:08X}",
        "blob_size": len(plan.blob),
        "n_items": N_ITEMS,
        "n_translated": n_translated,
        "patches": [{"offset": f"0x{p.offset:06X}",
                     "data": p.data.hex(" "),
                     "label": p.label} for p in patches],
        "blob_hex_head": plan.blob[:64].hex(" "),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\npatch 清单 → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
