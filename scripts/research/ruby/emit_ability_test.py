#!/usr/bin/env python3
"""特性名端到端验证包：生成 asm patch + 新表数据，可直接接入构建。

特性名（77 项）：
  base=0x1CBC44, stride 8→32（×4，净移位 +2）
  3 个 ldr 站点，K 全部 =8，已由符号执行精确识别
  可用宽度 8→32，最长译文 17B ✓

产出：
  1. patches/table_stride_test.asm  —— 3 处 lsls 改写
  2. gen/ability_table_test.asm     —— 新表数据（77 × 32 = 2464 B）

用法：
    python scripts/research/ruby/emit_ability_test.py
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

ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
HOOK = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook"

GBA_BASE = 0x08000000
BASE = 0x1CBC44
OLD_STRIDE = 8
NEW_STRIDE = 32
USABLE = 8
N = 77
EOS = 0xFF
DATA_ADDR = 0x09EB0000       # 新表起始（GBA 地址）


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
    if plan.skipped:
        for s in plan.skipped:
            print(f"  ⏭ 0x{s.ldr_off:06X} K={s.stride} {s.reason}")
    if plan.n_patches != plan.n_ldrs:
        print("  ❌ 未完全识别，中止")
        return 1

    lines = [
        "; " + "=" * 77,
        "; [测试] 特性名 stride 8→32（3 处 lsls 净移位 +2）",
        "; 生成器: scripts/research/ruby/emit_ability_test.py",
        "; 依据: 符号执行精确求出每站点 K=8，只改这些站点的移位指令",
        "; " + "=" * 77,
        "",
    ]
    for p in plan.patches:
        lines.append(f"; {p.label}")
        lines.append(f".org 0x{p.offset + GBA_BASE:08X}")
        lines.append(f"    .byte 0x{p.data[0]:02X}, 0x{p.data[1]:02X}")
        lines.append("")
    out_stride = HOOK / "patches" / "table_stride_test.asm"
    out_stride.write_text("\n".join(lines) + "\n", encoding="utf-8",
                          newline="\n")
    print(f"  → {out_stride}")

    # —— 2. 新表 ——
    print()
    print("=== 2. 新表（77 × 32）===")
    items = {}
    for e in (d.get("entries") or []):
        if e.get("module") != "特性名":
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
    meta = OLD_STRIDE - USABLE       # 0
    for i in range(N):
        src = BASE + i * OLD_STRIDE
        e = items.get(src)
        if e and (e.get("translated") or ""):
            body = encode_body(cm, e["translated"])
            n_trans += 1
            if len(body) > NEW_STRIDE:
                body = body[:NEW_STRIDE - 1] + bytes([EOS])
        else:
            body = rom[src:src + USABLE]
        blob += body + bytes([EOS]) * (NEW_STRIDE - len(body))

    print(f"  {n_trans} 项有译文，{len(blob):,} B")

    lines2 = [
        "; " + "=" * 77,
        "; [测试] 特性名新表（77 项 × 32 字节）",
        "; 生成器: scripts/research/ruby/emit_ability_test.py",
        "; " + "=" * 77,
        "",
        f".org 0x{DATA_ADDR:08X}",
        ".align 4",
        "TblAbilityNames:",
    ]
    for i in range(0, len(blob), 16):
        chunk = blob[i:i + 16]
        lines2.append("    .byte " + ", ".join(f"0x{b:02X}" for b in chunk))
    out_data = HOOK / "gen" / "ability_table_test.asm"
    out_data.write_text("\n".join(lines2) + "\n", encoding="utf-8",
                        newline="\n")
    print(f"  → {out_data}")

    # —— 3. relink 字面量 ——
    print()
    print("=== 3. relink 字面量（指向新表）===")
    import struct
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
        "; [测试] 特性名表基址重定向 → 0x%08X" % DATA_ADDR,
        "; " + "=" * 77,
        "",
    ]
    for lit in lits:
        lines3.append(f".org 0x{lit + GBA_BASE:08X}")
        lines3.append(f"    .word 0x{DATA_ADDR:08X}")
        lines3.append("")
    out_relink = HOOK / "patches" / "ability_relink_test.asm"
    out_relink.write_text("\n".join(lines3) + "\n", encoding="utf-8",
                          newline="\n")
    print(f"  {len(lits)} 处 → {out_relink}")

    print()
    print("=== 汇总 ===")
    print(f"  stride patch : {plan.n_patches} 处")
    print(f"  新表         : {len(blob):,} B @ 0x{DATA_ADDR:08X}")
    print(f"  字面量重定向 : {len(lits)} 处")
    print()
    print("接入方式（main.asm）：")
    print('  .include "./patches/table_stride_test.asm"')
    print('  .include "./patches/ability_relink_test.asm"')
    print('  .include "./gen/ability_table_test.asm"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
