#!/usr/bin/env python3
"""A2.6 执行：图鉴分类名 343 条（FIXED，零机器码）。

几何（待验证）：
  base=0x38474C, stride=28, name_offset=6, n=386
  cap = 28 - 6 = 22 字节

路径：整表搬新区，保持 stride=28，只改 7 处字面量。

步骤：
  1. 校验几何（ROM 字节 + build.json 地址吻合）
  2. 构造新表（整项复制，只替换 +0x06 的名字）
  3. 扩表 + 分配新区
  4. 生成 relink patch
  5. 输出 patch 清单（不写 ROM）

用法：
    python scripts/research/ruby/a2_pokedex_exec.py
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
OUT = ROOT / "work" / "_probe" / "a2_pokedex_patches.json"

GBA_BASE = 0x08000000
BASE = 0x38474C
STRIDE = 28
NAME_OFF = 6
N = 386
CAP = STRIDE - NAME_OFF          # 22
ALLOC_START = 0x09F10000         # 承接道具名之后
ALLOC_SIZE = 0x100000


def main() -> int:
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path
    from meowth.table_expand import (ExpandAllocator, expand_fixed,
                                     encode_body, describe)
    from meowth.table_relink import (find_literal_sites, find_ldr_literals,
                                     patch_literal)

    cm = Charmap(charmap_path=get_charmap_path("POKEMON_RUBY_AXVJ00"),
                 target_lang="zh-Hans")
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    # ---- 步骤 1：校验几何 ----
    print("=== 步骤 1：校验几何 ===")
    items = {}
    for e in d.get("entries") or []:
        if e.get("module") != "图鉴分类名":
            continue
        try:
            a = int(str(e.get("address") or "0x0").replace("0x", ""), 16)
        except ValueError:
            continue
        if a >= GBA_BASE:
            a -= GBA_BASE
        items[a] = e
    print(f"  build.json 条目 {len(items)}")

    # 抽验：条目地址 == BASE + i*STRIDE + NAME_OFF ?
    ok = 0
    for i in range(min(20, N)):
        expect = BASE + i * STRIDE + NAME_OFF
        if expect in items:
            ok += 1
    print(f"  前 20 项地址吻合 {ok}/20"
          + ("  ✅" if ok >= 18 else "  ❌ 几何可能不对"))

    # ROM 字节校验：每项 +0x06 处是否为合法文本（含 FF）
    rom_ok = 0
    for i in range(N):
        seg = rom[BASE + i * STRIDE + NAME_OFF:
                  BASE + i * STRIDE + NAME_OFF + CAP]
        if b"\xFF" in seg:
            rom_ok += 1
    print(f"  ROM 字节：{rom_ok}/{N} 项在 +0x{NAME_OFF:X} 处含 FF")

    if rom_ok < N * 0.9:
        print("  ❌ 几何校验失败，中止")
        return 1

    # ---- 步骤 2：构造新表 ----
    print()
    print("=== 步骤 2：构造新表（整项 28B 复制，替换 +0x06 的名字）===")
    bodies: list[bytes] = []
    n_trans = 0
    over = []

    for i in range(N):
        base_off = BASE + i * STRIDE
        item = bytearray(rom[base_off:base_off + STRIDE])
        name_at = base_off + NAME_OFF
        e = items.get(name_at)
        text = (e.get("translated") or "") if e else ""

        if text:
            n_trans += 1
            body = encode_body(cm, text)
            if len(body) > CAP:
                over.append((i, text, len(body)))
                body = body[:CAP - 1] + bytes([0xFF])
        else:
            orig = rom[name_at:name_at + CAP]
            ff = orig.find(b"\xFF")
            body = orig[:ff + 1] if ff >= 0 else orig

        names = body + bytes([0x00]) * (CAP - len(body))
        new_item = bytearray(item[:NAME_OFF]) + names
        # 保留原项 +0x06 之后的「非名字」部分？
        # 图鉴分类名的名称字段后面还有数据（eos=0 表示字段后是别的）
        # 实测：+0x00..+0x05 是头部，+0x06 起是名字，名字用 FF 结尾，
        #       FF 之后到 +0x1C 仍是本项数据，必须保留
        ff_orig = rom[name_at:name_at + CAP].find(b"\xFF")
        if ff_orig >= 0:
            tail = rom[name_at + ff_orig + 1:base_off + STRIDE]
            new_item = (bytearray(item[:NAME_OFF]) + body +
                        bytes([0x00]) * max(0, CAP - len(body) - len(tail)) +
                        tail)
        bodies.append(bytes(new_item[:STRIDE]).ljust(STRIDE, b"\x00"))

    print(f"  有译文 {n_trans}，超长 {len(over)}")
    for i, t, n in over[:5]:
        print(f"    item{i} {t!r} = {n}B > {CAP}B")

    # ---- 步骤 3：扩表 ----
    print()
    print("=== 步骤 3：扩表 + 分配新区 ===")
    alloc = ExpandAllocator(start=ALLOC_START, size=ALLOC_SIZE)
    plan = expand_fixed(
        name="图鉴分类名", orig_base=BASE, stride=STRIDE, n=N,
        bodies=bodies, alloc=alloc, name_offset=0,
    )
    print(f"  {describe(plan)}")
    print(f"  新区 0x{plan.new_base:06X}..0x{plan.new_base + len(plan.blob):06X}")

    # ---- 步骤 4：relink ----
    print()
    print("=== 步骤 4：relink ===")
    old_gba = GBA_BASE + BASE
    sites = find_literal_sites(rom, old_gba, require_aligned=True)
    print(f"  旧基址 0x{old_gba:08X} 的字面量 {len(sites)} 处")

    patches = []
    for s in sites:
        if struct.unpack_from("<I", rom, s)[0] != old_gba:
            continue
        ldrs = find_ldr_literals(rom, s)
        patches.append({
            "offset": f"0x{s:06X}",
            "old": f"0x{old_gba:08X}",
            "new": f"0x{GBA_BASE + plan.new_base:08X}",
            "data": struct.pack("<I", GBA_BASE + plan.new_base).hex(" "),
            "ldr": f"0x{ldrs[0]:X}" if ldrs else None,
        })
    print(f"  patch {len(patches)} 条")
    for p in patches:
        print(f"    0x{p['offset']:>10}: {p['data']}  "
              + (f"ldr@{p['ldr']}" if p["ldr"] else "裸指针"))

    # ---- 步骤 5：输出 ----
    print()
    print("=== 结果 ===")
    print(f"  新表 {len(plan.blob):,} B @0x{plan.new_base:06X}")
    print(f"  消灭 F980: {n_trans} 条")
    print(f"  机器码改动: 0 处（FIXED 模式）")
    print(f"  字面量改写: {len(patches)} 处")
    print()
    print(f"  塞得下: {N - len(over)}/{N}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "table": "图鉴分类名",
        "orig_base": f"0x{BASE:06X}",
        "new_base": f"0x{plan.new_base:06X}",
        "stride": STRIDE, "name_offset": NAME_OFF, "cap": CAP,
        "n_items": N, "n_translated": n_trans, "n_overflow": len(over),
        "blob_size": len(plan.blob),
        "patches": patches,
        "blob_head": plan.blob[:64].hex(" "),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
