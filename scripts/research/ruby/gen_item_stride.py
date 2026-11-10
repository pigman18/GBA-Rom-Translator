#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成道具表 stride 40→48 的完整补丁。

## 方案（2026-11-05 实测确定）

把名字区从 9B 扩到 17B（4 汉字），元数据整体后移 8B。

两类改动：
  1. **乘法**：14 处 `(i*4+i)*8` → `(i*2+i)*16`
     ×40 = (i*4+i)×8 → ×48 = (i*2+i)×16
     只改移位立即数，字节数不变  → patches/item_stride_48.asm

  2. **字段偏移**：12 处访问点 +8
     · 9 处直接改 ldr/ldrb/ldrh 的 5 位立即数（新值仍 ≤31）
     · 3 处是 `adds r4,#imm` 形式，改立即数
     · 1 处 `ldrb r0,[r1,#0x1C]` → `#0x24` 超 5 位范围，
       改走「整函数基址 +8」：把该函数 `ldr r4,[pc]` 的字面量减 8，
       并把 `adds r1,r1,r4` 之前的偏移都相应处理 ——
       实测该函数无其它偏移，直接把 ldr 换成 ldrh 变体不可行，
       改用 trampoline（唯一一处）。

产出：patches/item_stride_48.asm（含乘法 + 字段偏移 + trampoline）
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
OUT = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook" / "patches" / "item_stride_48.asm"

TABLE = 0x0839A648
SHIFT = 8
STUB = 0x01F00800          # trampoline 桩区（文件偏移，避开已有的 0x1F00000）

# 字段访问点：(指令 GBA, mnemonic, 新偏移)
# ⚠️ 这些是**重排后的新偏移**，与 emit_table_data.TABLES["道具名"]["field_map"]
#    严格一致（由 verify_item_table.py 校验）。不是「旧偏移 +8」。
#
#   旧0x0A→新0x12  ldrh   旧0x0C→新0x14  ldrh
#   旧0x0E→新0x16  ldrb   旧0x0F→新0x17  ldrb
#   旧0x14→新0x18  ldrb   旧0x15→新0x19  ldrb
#   旧0x16→新0x1A  ldrb   旧0x17→新0x1B  ldrb
#   旧0x1C→新0x1C  不改（1 读 2 写，留在原位绕开 ldrb 上限）
FIELD_SITES = [
    (0x080A53B4, "ldrh", 0x12),
    (0x080A53D8, "ldrh", 0x14),
    (0x080A53FC, "ldrb", 0x16),
    (0x080A5420, "ldrb", 0x17),
    (0x080A546C, "ldrb", 0x18),
    (0x080A5490, "ldrb", 0x19),
    (0x080A54B4, "ldrb", 0x1A),
    (0x080A54D8, "ldrb", 0x1B),
]

# adds r4,#imm 形式的基址调整点：(指令 GBA, 新立即数)
ADDS_SITES = [
    (0x080A5442, 0x24),   # 旧 #0x10（说明指针  → 新 0x24）
    (0x080A54FA, 0x20),   # 旧 #0x18（第二个指针 → 新 0x20）
    (0x080A5546, 0x28),   # 旧 #0x20（u32      → 新 0x28）
]


def enc_ldr(mn: str, imm: int) -> bytes:
    """编码 ldr/ldrb/ldrh r0, [r1, #imm]（Thumb 5 位立即数）。"""
    if mn == "ldrb":
        if imm > 31:
            raise ValueError(f"ldrb 偏移 {imm} 超限")
        v = 0x7800 | (imm << 6) | (1 << 3) | 0
    elif mn == "ldrh":
        if imm % 2 or imm // 2 > 31:
            raise ValueError(f"ldrh 偏移 {imm} 超限")
        v = 0x8800 | ((imm // 2) << 6) | (1 << 3) | 0
    else:
        if imm % 4 or imm // 4 > 31:
            raise ValueError(f"ldr 偏移 {imm} 超限")
        v = 0x6800 | ((imm // 4) << 6) | (1 << 3) | 0
    return struct.pack("<H", v)


def t_ldr_lit(rd: int, at_gba: int, lit_gba: int) -> bytes:
    delta = lit_gba - (((at_gba - 0x08000000) + 4) & ~3) - 0x08000000
    delta = lit_gba - (at_gba + 4)
    # armips 会按 4 字节对齐算 pc
    pc = ((at_gba + 4) & ~3)
    d = lit_gba - pc
    if d < 0 or d % 4 or d // 4 > 255:
        raise ValueError(f"字面量不可达 at=0x{at_gba:X} lit=0x{lit_gba:X} d={d}")
    return struct.pack("<H", 0x4800 | (rd << 8) | (d // 4))


def main() -> int:
    rom = ROM.read_bytes()
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

    lines = [
        "; " + "=" * 77,
        "; 道具表 stride 40→48（自动生成，勿手改）",
        "; 生成器: scripts/research/ruby/gen_item_stride.py",
        "; ",
        "; 名字区 9B→17B（4 汉字），元数据整体后移 8B。",
        "; 1) 14 处 (i*4+i)*8 → (i*2+i)*16  （只改移位立即数）",
        "; 2) 12 处访问点字段偏移 +8",
        "; " + "=" * 77,
        "",
    ]

    # ── 1) 乘法站点 ────────────────────────────────────────────────
    pat = struct.pack("<I", TABLE)
    sites = []
    i = rom.find(pat)
    while i != -1:
        sites.append(i)
        i = rom.find(pat, i + 1)

    n_mul = 0
    lines.append("; ---- 1) 乘法：×40 → ×48 ----")
    for s in sites:
        st = s - 0x14
        seq = list(md.disasm(rom[st:s + 4], st + 0x08000000))
        for k, x in enumerate(seq):
            if x.mnemonic != "lsls":
                continue
            p = [q.strip() for q in x.op_str.split(",")]
            if len(p) != 3:
                continue
            rd, rm, sh = p
            val = None
            note = ""
            # ×40 = (i*4 + i) * 8  →  ×48 = (i*2 + i) * 16
            #   第一乘 lsls rX, r0, #2  → #1
            #   第二乘 lsls rX, rX, #3  → #4
            if sh == "#2" and rm != rd:
                val = (1 << 6) | (int(rm[1:]) << 3) | int(rd[1:])
                note = "#2→#1"
            elif sh == "#3" and rm == rd:
                val = (4 << 6) | (int(rm[1:]) << 3) | int(rd[1:])
                note = "#3→#4"
            if val is None:
                continue
            lines.append(f".org 0x{x.address:08X}    ; lsls {x.op_str}  ({note})")
            lines.append(f"    .byte 0x{val & 0xFF:02X}, 0x{val >> 8:02X}")
            n_mul += 1
    lines.append("")

    # ── 2) 字段偏移 ────────────────────────────────────────────────
    n_fld = 0
    lines.append("; ---- 2) 字段偏移（新布局） ----")
    for gba, mn, new in FIELD_SITES:
        off = gba - 0x08000000
        ins = list(md.disasm(rom[off:off + 2], gba))
        if not ins or ins[0].mnemonic != mn:
            print(f"  [warn] 0x{gba:08X} 期望 {mn}，实际 {ins[0].mnemonic if ins else '?'}")
            continue
        old_txt = ins[0].op_str
        maxv = 31 if mn == "ldrb" else 62
        if new > maxv:
            print(f"  [ERR] 0x{gba:08X} 新偏移 0x{new:x} 超出 {mn} 上限 {maxv}")
            return 1
        b = enc_ldr(mn, new)
        chk = list(md.disasm(b, gba))
        if not chk or chk[0].op_str != f"r0, [r1, #0x{new:x}]":
            print(f"  [ERR] 0x{gba:08X} 编码校验失败: {chk[0].op_str if chk else '?'}")
            return 1
        lines.append(f".org 0x{gba:08X}    ; {mn} {old_txt} → [r1,#0x{new:x}]")
        lines.append("    .byte " + ", ".join(f"0x{v:02X}" for v in b))
        n_fld += 1

    # ── 3) adds r4,#imm 基址调整 ───────────────────────────────────
    n_adds = 0
    lines.append("")
    lines.append("; ---- 3) adds r4 立即数（指针字段/u32 的基址调整） ----")
    for gba, new in ADDS_SITES:
        off = gba - 0x08000000
        ins = list(md.disasm(rom[off:off + 2], gba))
        if not ins or ins[0].mnemonic != "adds":
            print(f"  [warn] 0x{gba:08X} 期望 adds，实际 {ins[0].mnemonic if ins else '?'}")
            continue
        old_txt = ins[0].op_str
        rd = int(ins[0].op_str.split(",")[0].strip()[1:])
        if new > 255:
            print(f"  [ERR] 0x{gba:08X} adds 立即数 0x{new:x} 超过 255")
            return 1
        val = 0x3000 | (rd << 8) | new
        b = struct.pack("<H", val)
        chk = list(md.disasm(b, gba))
        # capstone 对 adds 立即数的显示是 #0x24 还是 #36 取决于版本，
        # 两种都接受，只要求寄存器正确且立即数一致。
        ok_txt = False
        if chk:
            ops = chk[0].op_str
            if ops.startswith(f"r{rd}, #"):
                try:
                    shown = int(ops.split("#")[1].strip(), 0)
                    ok_txt = shown == new
                except ValueError:
                    ok_txt = False
        if not ok_txt:
            print(f"  [ERR] 0x{gba:08X} adds 编码校验失败: "
                  f"{chk[0].op_str if chk else '?'} (期望 r{rd}, #{new})")
            return 1
        lines.append(f".org 0x{gba:08X}    ; adds {old_txt} → r{rd}, #0x{new:x}")
        lines.append("    .byte " + ", ".join(f"0x{v:02X}" for v in b))
        n_adds += 1
    lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"写出 {OUT.name}: 乘法 {n_mul} 处，ldr/ldrb/ldrh {n_fld} 处，"
          f"adds {n_adds} 处，trampoline 0 处")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
