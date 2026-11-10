#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""道具表 stride 40→48 的字段偏移修正补丁。

## 背景

道具名原 entry 40 字节：
```
+00..+08  名字 8B + FF          (usable = 9)
+09       EOS/填充
+0A..+0F  u16 ×2（?）+ u8 ×2
+10       ▸ 说明文本指针
+14..+17  u8 ×4
+18       ▸ 另一个指针
+1C       u8
+20       u32
```

名字区只有 9B，中文 2 字正好 9B，但 281 条译文里只有 13 条 ≤2 字。
所以 stride 扩到 48，名字区扩到 17B（4 汉字）。

代价：**元数据整体后移 8 字节**（17-9=8），所有访问函数的固定偏移
必须同步 +8，否则游戏读到名字尾部。

## 做法

14 个访问函数里，读字段的指令形如：
```
ldrb r0, [r1, #0xe]     ; 2 字节指令，立即数 5 位（0..31）
```
偏移 +8 后会超过 31（如 0x20+8=0x28），5 位立即数放不下 ⇒ 必须用
`adds r1, #8` 先调整指针，但这会多吃一条指令、多占 2 字节，原地放不下。

⇒ 采用 trampoline：在原指令处放 `ldr r2,[pc,#0]` + `bx r2` + 桩地址，
  桩里做 `adds r1,#8` 再执行原指令并跳回。
"""
from __future__ import annotations

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
OUT = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook" / "patches" / "item_trampoline.asm"

TABLE_GBA = 0x0839A648
OLD_STRIDE = 40
NEW_STRIDE = 48
SHIFT = 8                       # 元数据后移字节数
STUB_AREA = 0x01F00000          # trampoline 区（文件偏移）

# 14 个访问函数的字段访问点：(指令文件偏移, mnemonic, 原偏移, 寄存器)
# 由 scripts/research/ruby/plan_item_stride.py 实测得出
ACCESS = [
    (0x0A538E, "ldrh", 0x0A, 1),   # ldrh r0,[r1,#0xa]  —— 注意 ldrh 支持 5位立即数*2
    (0x0A53B2, "ldrh", 0x0C, 1),
    (0x0A53D6, "ldrb", 0x0E, 1),
    (0x0A53FA, "ldrb", 0x0F, 1),
    (0x0A5442, "ldr",  0x10, 4),   # 指针字段
    (0x0A5452, "ldrb", 0x14, 1),
    (0x0A5476, "ldrb", 0x15, 1),
    (0x0A549A, "ldrb", 0x16, 1),
    (0x0A54BE, "ldrb", 0x17, 1),
    (0x0A54E0, "ldr",  0x18, 4),
    (0x0A5508, "ldrb", 0x1C, 1),
    (0x0A552C, "ldr",  0x20, 4),
    (0x0A5554, "ldrb", 0x00, 1),
    (0x0A557C, "ldrb", 0x24, 1),
]


def t_adds_imm(rd: int, imm: int) -> bytes:
    """adds rd, #imm（Thumb，imm 0..255）。"""
    return struct.pack("<H", 0x3000 | (rd << 8) | imm)


def t_ldr_lit(rd: int, at_file: int, lit_file: int) -> bytes:
    """ldr rd, [pc, #imm] —— imm = (lit - ((at+4)&~3)) / 4。"""
    delta = lit_file - ((at_file + 4) & ~3)
    if delta % 4 or not (0 <= delta // 4 <= 255):
        raise ValueError(f"字面量不可达: at=0x{at_file:X} lit=0x{lit_file:X}")
    return struct.pack("<H", 0x4800 | (rd << 8) | (delta // 4))


def t_bx(rm: int) -> bytes:
    return struct.pack("<H", 0x4700 | (rm << 3))


def main() -> int:
    rom = ROM.read_bytes()
    print(f"道具表 0x{TABLE_GBA:08X}  stride {OLD_STRIDE}→{NEW_STRIDE}  元数据后移 {SHIFT}B")
    print()

    # 逐条核对原指令，防止偏移与实测脱节
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    lines = [
        "; " + "=" * 77,
        "; 道具表 stride 40→48：14 个访问函数的字段偏移 +8（自动生成，勿手改）",
        "; 生成器: scripts/research/ruby/gen_item_trampoline.py",
        "; ",
        "; 为什么要 trampoline：字段偏移 +8 后（如 0x1C→0x24）超出 Thumb",
        "; ldr/ldrb 的 5 位立即数范围（0..31），无法原地改立即数。",
        "; 桩做 adds r1,#8 后重放原指令，再跳回。",
        "; " + "=" * 77,
        "",
    ]

    stub = STUB_AREA
    n_ok = 0
    for off, mn, old_imm, width in ACCESS:
        ins = list(md.disasm(rom[off:off + 4], off + 0x08000000))
        if not ins:
            print(f"  [skip] 0x{off + 0x08000000:08X} 无法反汇编")
            continue
        x = ins[0]
        new_imm = old_imm + SHIFT
        note = ""
        # 5 位立即数上限：ldrb 0..31；ldrh 0..31（×2=0..62）；ldr 0..31（×4）
        limit = 31 if width == 1 else 124
        if width == 2:
            limit = 62
        if new_imm <= limit:
            note = "（可原地改立即数，无需 trampoline）"
            print(f"  0x{x.address:08X}  {x.mnemonic} {x.op_str} → 偏移 0x{new_imm:02X}{note}")
            # 原地改：重新编码
            lines.append(f"; 0x{x.address:08X}  {x.mnemonic} {x.op_str} → [r1,#0x{new_imm:x}]")
            lines.append(f".org 0x{x.address:08X}")
            imm5 = new_imm if width == 1 else new_imm // width
            rt = 0
            rm = 1
            val = 0x6800 | (imm5 << 6) | (rm << 3) | rt    # ldr
            if mn == "ldrb":
                val = 0x7800 | (imm5 << 6) | (rm << 3) | rt
            elif mn == "ldrh":
                val = 0x8800 | (imm5 << 6) | (rm << 3) | rt
            lines.append(f"    .byte 0x{val & 0xFF:02X}, 0x{val >> 8:02X}")
            lines.append("")
            n_ok += 1
            continue

        print(f"  0x{x.address:08X}  {x.mnemonic} {x.op_str} → 偏移 0x{new_imm:02X} 需 trampoline")
        lines.append(f"; 0x{x.address:08X}  {x.mnemonic} {x.op_str} → [r1,#0x{new_imm:x}]  (trampoline)")
        lines.append(f".org 0x{x.address:08X}")
        # 原地 8 字节：ldr r2,[pc,#0] / bx r2 / 桩地址
        lit = (x.address - 0x08000000) + 8
        lines.append("    .byte " + ", ".join(
            f"0x{b:02X}" for b in t_ldr_lit(2, x.address - 0x08000000, lit)))
        lines.append("    .byte " + ", ".join(f"0x{b:02X}" for b in t_bx(2)))
        lines.append(f"    .word 0x{stub + 0x08000000:08X}")
        lines.append("")
        n_ok += 1

    lines.append(f"; ---- trampoline 桩区 0x{stub + 0x08000000:08X} ----")
    lines.append(f".org 0x{stub + 0x08000000:08X}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print()
    print(f"写出 {OUT.name}：{n_ok} 处")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
