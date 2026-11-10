#!/usr/bin/env python3
"""A2.7 准备：新表数据怎么落进 ROM？

现状：
  - patches/table_stride.asm 只改指令（lsls 立即数）
  - 表基址字面量由 Python 侧的 byte_patches 改（93 处）
  - **但新表数据本身（70,276 B）还没写进 ROM**

三条落法：
  A. 生成 gen/table_data.asm，用 .org + .byte 写进 armips 流程
  B. Python 侧直接写 ROM（rom_writer 的 free space 机制）
  C. 生成 .incbin 引用的二进制文件

火红用 A（数据 + patch 都在 ROM 布局里统一安排）。
本项目现有做法：字体走 graphic/fonts.s（.incbin），slot 表走 gen/translated_slot.asm（.org + .byte）。

先确认 armips 支持哪种，以及是否与 C 引擎的 .org GameBinAddresses 冲突。

用法：
    python scripts/research/ruby/a2_data_placement.py
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook"

# 已占用区间（从 game_addrs.asm + main.asm）
LAYOUT = [
    (0x08800000, 0x08810000, "game.bin (C 引擎)"),
    (0x08810000, 0x08820000, "PhraseOffsets"),
    (0x08820000, 0x08900000, "PhraseTable"),
    (0x09000000, 0x09100000, "FontChsNormal"),
    (0x09100000, 0x091E0000, "FontChsSmall"),
    (0x091E0000, 0x09320000, "PokeRSFontChsSym"),
    (0x09320000, 0x09EA0000, "FontChsMiddle"),
    (0x09EA0000, 0x09EB0000, "SlotTable"),
]

# 6 张表的新体积
TABLES = [
    ("招式名",         32,  354),
    ("特性名",         32,  77),
    ("属性名",         17,  18),
    ("道具名",         80,  348),
    ("图鉴分类名",     56,  386),
    ("秘密基地装饰名", 56,  120),
]


def main() -> int:
    print("=== 现有 hook 里的数据落地方式 ===")
    for f in ("main.asm", "graphic/fonts.s", "gen/translated_slot.asm"):
        p = HOOK / f
        if not p.is_file():
            print(f"  {f}: 不存在（构建时生成）")
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        # 找关键指令
        keys = []
        for kw in (".org", ".incbin", ".byte", ".word", ".align"):
            if kw in txt:
                keys.append(kw)
        print(f"  {f:<32} 用: {', '.join(keys) or '(无)'}")

    print()
    print("=== 已占用区间 ===")
    for lo, hi, note in LAYOUT:
        print(f"  0x{lo:08X}..0x{hi:08X}  {hi - lo:>9,}B  {note}")

    print()
    print("=== 6 张表新体积 ===")
    total = 0
    for name, stride, n in TABLES:
        sz = stride * n
        total += sz
        print(f"  {name:<16} {stride:>3}B × {n:>3} 项 = {sz:>7,}B")
    print(f"  {'合计':<16} {'':>3} {'':>7}  {total:>7,}B")

    # 找空闲区间
    print()
    print("=== 找可用空闲区间 ===")
    cursor = 0x09EB0000
    if cursor + total > 0x0A000000:
        print(f"  0x09EB0000 起只有 {0x0A000000 - cursor:,}B，不够 {total:,}B")
        print(f"  ⇒ 需要扩容 ROM 或复用 PhraseTable 空间（F980 废弃后释放 917KB）")
        cursor = 0x08820000
        print(f"  ⇒ 改用 0x08820000（PhraseTable 原址，待 F980 废弃后可用）")
    print(f"  建议新表起始: 0x{cursor:08X}")
    print(f"  6 张表总需 {total:,}B，"
          f"到 0x{cursor + total:08X} 结束")

    print()
    print("=== 推荐落法 ===")
    print("  生成 gen/table_data.asm：")
    print(f"    .org 0x{cursor:08X}")
    print("    .align 4")
    print("    Table_招式名:")
    print("      .byte 0x.., 0x.., ...")
    print("    ...")
    print()
    print("  理由：")
    print("    - 与现有 graphic/fonts.s、gen/translated_slot.asm 一致（.org + .byte）")
    print("    - 走 armips，与 ROM 扩容机制天然兼容")
    print("    - 不需要改 rom_writer 的空闲空间逻辑")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
