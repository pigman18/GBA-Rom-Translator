#!/usr/bin/env python3
"""A2.7 执行：生成 gen/table_data.asm（6 张表新数据）+ 字节 patch 清单。

流程（对应 docs/ALGO_PIPELINE.md 的 ③ PLACE + ④ RELINK）：
  1. 跑通用流水线，得到 6 张表的新字节 + 字面量 patch
  2. 生成 gen/table_data.asm：.org 0x09EB0000 + 各表 .byte
  3. 生成 work/_probe/a2_byte_patches.json：字面量改写清单
     （由 rom_writer 在打包时应用，或直接转成 patches/*.asm）

为什么要两份：
  - 表数据走 armips（.org + .byte），与 fonts.s/slot.asm 一致
  - 字面量改写也走 armips（.org + .word），最干净

用法：
    python scripts/research/ruby/a2_emit_table_data.py
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
HOOK = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook"
OUT_DATA = HOOK / "gen" / "table_data.asm"
OUT_RELINK = HOOK / "patches" / "table_relink.asm"
OUT_JSON = ROOT / "work" / "_probe" / "a2_emit_result.json"

GBA_BASE = 0x08000000
DATA_START = 0x01EB0000      # SlotTable(0x09EB0000 GBA) 之后的**文件偏移**

TABLES = {
    "招式名":         {"base": 0x1CACFC, "stride": 8,  "usable": 8,
                       "new_stride": 32, "new_usable": 32,
                       "n": 354, "eos": 0xFF, "name_offset": 0,
                       "sym": "TblMoveNames"},
    "特性名":         {"base": 0x1CBC44, "stride": 8,  "usable": 8,
                       "new_stride": 32, "new_usable": 32,
                       "n": 77,  "eos": 0xFF, "name_offset": 0,
                       "sym": "TblAbilityNames"},
    "属性名":         {"base": 0x1CBB0C, "stride": 5,  "usable": 5,
                       "new_stride": 17, "new_usable": 17,
                       "n": 18,  "eos": 0xFF, "name_offset": 0,
                       "sym": "TblTypeNames"},
    "道具名":         {"base": 0x39A648, "stride": 40, "usable": 9,
                       "new_stride": 80, "new_usable": 49,
                       "n": 348, "eos": 0xFF, "name_offset": 0,
                       "sym": "TblItemNames"},
    "图鉴分类名":     {"base": 0x38474C, "stride": 28, "usable": 6,
                       "new_stride": 56, "new_usable": 34,
                       "n": 386, "eos": 0x00, "name_offset": 0,
                       "sym": "TblSpeciesCategory"},
    "秘密基地装饰名": {"base": 0x3C2A44, "stride": 28, "usable": 10,
                       "new_stride": 56, "new_usable": 38,
                       "n": 120, "eos": 0xFF, "name_offset": 1,
                       "sym": "TblDecorNames"},
}


def emit_bytes_asm(blob: bytes, indent: str = "    ", per_line: int = 16) -> list[str]:
    """把字节渲染成 .byte 行。"""
    lines = []
    for i in range(0, len(blob), per_line):
        chunk = blob[i:i + per_line]
        body = ", ".join(f"0x{b:02X}" for b in chunk)
        lines.append(f"{indent}.byte {body}")
    return lines


def main() -> int:
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path
    from meowth.text_pipeline import run_pipeline
    from meowth.region_alloc import RegionAllocator
    from meowth.table_relink import AsmPatch, generate_asm_patches

    cm = Charmap(charmap_path=get_charmap_path("POKEMON_RUBY_AXVJ00"),
                 target_lang="zh-Hans")
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    entries = [e for e in (d.get("entries") or [])
               if e.get("type") == "replace"
               and e.get("phrase_code") is not None
               and (e.get("module") or "") in TABLES]

    print(f"条目 {len(entries):,}，跑流水线…")

    def encoder(text: str) -> bytes:
        b = cm.encode(text)
        return bytes(b) if b.endswith(b"\xFF") else bytes(b) + b"\xFF"

    # 固定从 DATA_START 开始，保证 .asm 里的 .org 可预测
    alloc = RegionAllocator(start=DATA_START, end=0x02000000)  # 到 32MB
    result = run_pipeline(
        rom=rom, entries=entries, tables=TABLES,
        encoder=encoder, alloc=alloc, only_tables=True,
    )

    if result.tables:
        print(f"  6 张表，新区 0x{DATA_START + GBA_BASE:08X} 起（文件偏移 0x{DATA_START:06X}）")

    # ---- 生成 gen/table_data.asm ----
    lines = [
        "; " + "=" * 77,
        "; 6 张定长表的新数据（自动生成，勿手改）",
        "; 生成器: scripts/research/ruby/a2_emit_table_data.py",
        ";",
        "; 每张表由 meowth.text_pipeline 的 PLACE 阶段产出：",
        ";   整项 = [name_offset 头部][名字 usableB][eos 填充][元数据]",
        "; 基址由 patches/table_relink.asm 改字面量指过来。",
        "; " + "=" * 77,
        "",
    ]

    # 按流水线分配顺序输出（保证 .org 与实际一致）
    total = 0
    emitted = []
    for t in result.tables:
        base, blob = result.table_blobs[t.name]      # base = 文件偏移
        g = TABLES[t.name]
        total += len(blob)
        gba = GBA_BASE + base                         # 转 GBA 地址（只一次）
        emitted.append((t.name, gba, len(blob), g["new_stride"], g["sym"]))

        lines.append(f"; ---- {t.name}: {len(blob):,}B  "
                     f"stride {g['stride']}→{g['new_stride']}  "
                     f"{g['n']} 项 ----")
        lines.append(f".org 0x{gba:08X}")
        lines.append(".align 4")
        lines.append(f"{g['sym']}:")
        lines.extend(emit_bytes_asm(blob))
        lines.append("")

    OUT_DATA.parent.mkdir(parents=True, exist_ok=True)
    OUT_DATA.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    # ---- 生成 patches/table_relink.asm（改基址字面量）----
    asm_patches = []
    for p in result.byte_patches:
        offs = p.offset
        if isinstance(offs, str):
            offs = int(offs.replace("0x", ""), 16)
        asm_patches.append(AsmPatch(
            offset=(offs if offs >= GBA_BASE else offs + GBA_BASE),
            bytes_=p.data,
            comment=p.label,
        ))

    header = (
        "; " + "=" * 77 + "\n"
        "; 表基址重定向：把指向旧表的字面量改成新表地址（自动生成，勿手改）\n"
        "; 生成器: scripts/research/ruby/a2_emit_table_data.py\n"
        "; 数据在 gen/table_data.asm\n"
        "; " + "=" * 77
    )
    OUT_RELINK.parent.mkdir(parents=True, exist_ok=True)
    OUT_RELINK.write_text(
        generate_asm_patches(asm_patches, header=header),
        encoding="utf-8", newline="\n",
    )

    # ---- 报告 ----
    print()
    print("=== 生成的表数据 ===")
    print(f"{'表':<16} {'基址':>12} {'体积':>9} {'stride':>7} {'符号'}")
    for name, base, size, stride, sym in emitted:
        print(f"{name:<16} 0x{base:08X} {size:>9,} {stride:>7} {sym}")
    print(f"{'合计':<16} {'':>12} {total:>9,}")

    print()
    print(f"=== 字面量 patch: {len(asm_patches)} 处 ===")
    for p in asm_patches[:6]:
        print(f"  0x{p.offset:08X}  {p.bytes_.hex(' ')}  {p.comment}")
    if len(asm_patches) > 6:
        print(f"  … 另 {len(asm_patches) - 6} 处")

    print()
    print(f"→ {OUT_DATA}  ({OUT_DATA.stat().st_size:,} B)")
    print(f"→ {OUT_RELINK}  ({OUT_RELINK.stat().st_size:,} B)")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({
        "tables": [
            {"name": n, "base": f"0x{b:08X}", "size": s,
             "stride": sd, "sym": sym}
            for n, b, s, sd, sym in emitted
        ],
        "total_bytes": total,
        "relink_patches": len(asm_patches),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
