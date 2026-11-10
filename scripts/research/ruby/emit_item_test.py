#!/usr/bin/env python3
"""执行道具名表：14/14 站点 K 全部 =40，100% 确定。

道具名（348 项）：
  base=0x39A648, stride 40→80（×2，净移位 +1）
  14 个 ldr 站点，K 全部 =40（符号执行 100% 确定）
  名字区 9B → 49B，最长译文 29B ✓

产出：
  patches/item_stride_test.asm   —— 14 处 lsls #3→#4
  patches/item_relink_test.asm   —— 字面量 → 新表
  gen/item_table_test.asm        —— 新表（348 × 80 = 27840 B）

用法：
    python scripts/research/ruby/emit_item_test.py
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

ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
HOOK = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook"

GBA_BASE = 0x08000000
BASE = 0x39A648
OLD_STRIDE = 40
NEW_STRIDE = 80
USABLE = 9          # 名字区（100% 合规判据）
N = 348
EOS = 0xFF
DATA_ADDR = 0x09EC0000       # 新表位置（避开特性名的 0x09EB0000）


def main() -> int:
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path
    from meowth.table_expand import encode_body
    from meowth.table_stride import plan_stride_rewrite

    cm = Charmap(charmap_path=get_charmap_path("POKEMON_RUBY_AXVJ00"),
                 target_lang="zh-Hans")
    rom = ROM.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    # —— 1. stride patch ——
    plan = plan_stride_rewrite(rom, BASE, OLD_STRIDE, NEW_STRIDE)
    print(f"=== 1. stride patch：{plan.n_patches}/{plan.n_ldrs} 站点 ===")
    for p in plan.patches:
        print(f"  0x{p.offset:06X}: {p.data.hex(' ')}  {p.label}")
    for s in plan.skipped:
        print(f"  ⏭ 0x{s.ldr_off:06X} K={s.stride} {s.reason}")
    if plan.n_patches != plan.n_ldrs:
        print("  ❌ 未完全识别，中止")
        return 1

    lines = [
        "; " + "=" * 77,
        "; [测试] 道具名 stride 40→80（%d 处 lsls 净移位 +1）" % plan.n_patches,
        "; 生成器: scripts/research/ruby/emit_item_test.py",
        "; 依据: 符号执行求出每站点 K=40，只改这些站点的移位指令",
        "; " + "=" * 77,
        "",
    ]
    for p in plan.patches:
        lines.append(f"; {p.label}")
        lines.append(f".org 0x{p.offset + GBA_BASE:08X}")
        lines.append(f"    .byte 0x{p.data[0]:02X}, 0x{p.data[1]:02X}")
        lines.append("")
    (HOOK / "patches" / "item_stride_test.asm").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"  → item_stride_test.asm")

    # —— 2. 新表 ——
    print()
    print("=== 2. 新表（348 × 80）===")
    items = {}
    for e in (d.get("entries") or []):
        if e.get("module") != "道具名":
            continue
        if e.get("type") != "replace" or e.get("phrase_code") is None:
            continue
        try:
            a = int(str(e.get("address") or "0x0").replace("0x", ""), 16)
        except ValueError:
            continue
        if a >= GBA_BASE:
            a -= GBA_BASE
        items[a] = e

    blob = bytearray()
    n_trans = 0
    meta = OLD_STRIDE - USABLE       # 40 - 9 = 31
    name_cap = NEW_STRIDE - meta     # 80 - 31 = 49
    for i in range(N):
        src = BASE + i * OLD_STRIDE
        e = items.get(src)
        if e and (e.get("translated") or ""):
            body = encode_body(cm, e["translated"])
            n_trans += 1
            if len(body) > name_cap:
                body = body[:name_cap - 1] + bytes([EOS])
        else:
            body = rom[src:src + USABLE]
        blob += body + bytes([EOS]) * (name_cap - len(body))
        # 元数据原样保留
        blob += rom[src + USABLE:src + OLD_STRIDE]

    print(f"  {n_trans} 项有译文，{len(blob):,} B")

    lines2 = [
        "; " + "=" * 77,
        "; [测试] 道具名新表（348 项 × 80 字节）",
        "; 生成器: scripts/research/ruby/emit_item_test.py",
        "; " + "=" * 77,
        "",
        f".org 0x{DATA_ADDR:08X}",
        ".align 4",
        "TblItemNames:",
    ]
    for i in range(0, len(blob), 16):
        chunk = blob[i:i + 16]
        lines2.append("    .byte " + ", ".join(f"0x{b:02X}" for b in chunk))
    (HOOK / "gen" / "item_table_test.asm").write_text(
        "\n".join(lines2) + "\n", encoding="utf-8", newline="\n")
    print(f"  → item_table_test.asm")

    # —— 3. relink ——
    print()
    print("=== 3. relink 字面量 ===")
    needle = struct.pack("<I", BASE + GBA_BASE)
    lits, s = [], 0
    while True:
        i = rom.find(needle, s)
        if i < 0:
            break
        if i % 4 == 0:
            lits.append(i)
        s = i + 1
    lines3 = [
        "; " + "=" * 77,
        "; [测试] 道具名表基址重定向 → 0x%08X" % DATA_ADDR,
        "; " + "=" * 77,
        "",
    ]
    for lit in lits:
        lines3.append(f".org 0x{lit + GBA_BASE:08X}")
        lines3.append(f"    .word 0x{DATA_ADDR:08X}")
        lines3.append("")
    (HOOK / "patches" / "item_relink_test.asm").write_text(
        "\n".join(lines3) + "\n", encoding="utf-8", newline="\n")
    print(f"  {len(lits)} 处 → item_relink_test.asm")

    print()
    print("=== 汇总 ===")
    print(f"  stride patch : {plan.n_patches} 处")
    print(f"  新表         : {len(blob):,} B @ 0x{DATA_ADDR:08X}")
    print(f"  字面量       : {len(lits)} 处")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
