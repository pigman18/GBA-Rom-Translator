#!/usr/bin/env python3
"""查 ruby 定长名称表的「基址」在代码里怎么被加载。

背景：上一支脚本证明 7/8 张表是 INLINE_STRUCT（基址+偏移访问，元素无独立指针）。
火红对同类块的做法是「改字面量池里的基址常量」指向新表（FIRERED_FULL_LOGIC §3.1 形态 B）。
本脚本验证 ruby 这边是否也存在这样的基址字面量。

判据：
  某个表的名称字段基址 A 若以 u32 形式出现在 ROM 里，且位于代码段
  → 该字面量被 ldr [pc, #n] 加载，是可 patch 的锚点

用法：
    python scripts/research/ruby/probe_table_base_literals.py
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
CODE_END = 0x081C0000  # 粗略：0x08000000 起的大部分是代码+字面量池

TARGETS = [
    "招式名", "道具名", "图鉴分类名", "秘密基地装饰名",
    "属性名", "特性名", "树果名", "性格名",
]


def parse_hex(s) -> int:
    return int(str(s).replace("0x", "").replace("0X", ""), 16)


def find_literal_sites(rom: bytes, target_gba: int) -> list[int]:
    """找 ROM 里所有等于 target_gba 的 4 字节对齐 u32 的文件偏移。"""
    needle = struct.pack("<I", target_gba)
    sites: list[int] = []
    start = 0
    while True:
        i = rom.find(needle, start)
        if i < 0:
            break
        if i % 4 == 0:
            sites.append(i)
        start = i + 1
    return sites


def is_arm_ldr_literal(rom: bytes, lit_off: int) -> tuple[bool, int]:
    """判断某字面量是否被前向的 ldr [pc, #imm] 引用。

    ARM/Thumb 都可能；这里只做粗判：往前 4096 字节内，
    找 thumb `ldr rX,[pc,#imm]` 形态（01001 Rt IIIIIIII），
    计算目标 = (该指令地址+4 对齐) + imm*4，与 lit_off 相等即命中。
    """
    lo = max(0, lit_off - 4096)
    for off in range(lo, lit_off, 2):
        hw = struct.unpack_from("<H", rom, off)[0]
        if (hw & 0xF800) != 0x4800:  # thumb ldr rX,[pc,#imm8]
            continue
        imm = (hw & 0xFF) * 4
        pc = ((off + 4) & ~3)
        if pc + imm == lit_off:
            return True, off
    return False, -1


def main() -> int:
    rom = ROM.read_bytes()
    mods = (json.loads(TEXTS.read_text(encoding="utf-8")).get("modules") or {})
    print(f"ROM: {ROM.name}  {len(rom):,} B\n")

    rows = []
    for name in TARGETS:
        meta = mods.get(name)
        if not meta:
            continue
        start = parse_hex(meta["start"])
        read = meta.get("read") or {}
        noff = int(read.get("name_offset") or 0)
        base_gba = start + noff + GBA_BASE

        sites = find_literal_sites(rom, base_gba)
        code_sites = [s for s in sites if s < CODE_END]
        confirmed = []
        for s in code_sites:
            ok, ins = is_arm_ldr_literal(rom, s)
            if ok:
                confirmed.append((s, ins))

        rows.append({
            "module": name,
            "base_gba": f"0x{base_gba:08X}",
            "literal_sites": [f"0x{s:X}" for s in sites],
            "code_sites": [f"0x{s:X}" for s in code_sites],
            "ldr_confirmed": [{"literal": f"0x{s:X}", "ldr": f"0x{i:X}"} for s, i in confirmed],
        })

        print(f"=== {name} ===  基址 0x{base_gba:08X}")
        print(f"  全 ROM 字面量命中 {len(sites)} 处，其中代码段(<0x{CODE_END:X}) {len(code_sites)} 处")
        if code_sites:
            print(f"  代码段字面量: " + ", ".join(f"0x{s:X}" for s in code_sites[:8]))
        if confirmed:
            print(f"  ✅ 确认被 ldr[pc] 引用 {len(confirmed)} 处（可 patch 的锚点）")
            for s, i in confirmed[:5]:
                print(f"     字面量 0x{s:X} ← ldr @ 0x{i:X}")
        else:
            print("  ❌ 未确认 ldr 引用（可能基址在运行时算出来，或引用点在 4KB 外）")
        print()

    out = ROOT / "work" / "_probe" / "ruby_table_base_literals.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"rom": ROM.name, "rows": rows}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"结果 → {out}")
    n = sum(1 for r in rows if r["ldr_confirmed"])
    print(f"\n汇总: {n}/{len(rows)} 张表找到可 patch 的基址字面量")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
