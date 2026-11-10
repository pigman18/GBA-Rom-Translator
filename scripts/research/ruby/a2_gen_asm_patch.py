#!/usr/bin/env python3
"""生成 6 张表的 stride 改动 asm patch。

参考 patches/pokedex.asm 的做法：
  常量写进 game_addrs.asm（equ），值改动写进 patches/*.asm（.org + 指令）

本脚本需要先反汇编确认每张表的「乘法指令位置」与「立即数」，
才能生成正确的 patch。

已知乘法（前面反汇编实测）：
  招式名       0x02B538: lsls r1, r1, #3       (×8)
  特性名       0x09C6C2: lsls r0, r4, #3       (×8)
  属性名       0x02B6AC: lsls r1, r0, #2 + adds  (×5)  ← 非 2 幂，需另一套改法
  道具名       0x0A5388: lsls #2 + adds + lsls #3 (×40) ← 非 2 幂
  图鉴分类名   0x08C1D0: lsls #3 + subs + lsls #2  (×28) ← 非 2 幂
  秘密基地装饰名 0x0AF2D2: 同 ×28 + adds #0x14

只有 2 的幂（×8）能靠改单个移位立即数。
其余是非 2 幂的乘法展开，改法不同。

用法：
    python scripts/research/ruby/a2_gen_asm_patch.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import capstone

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
OUT = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook" / "patches" / "table_stride.asm"
GBA_BASE = 0x08000000

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

# (表名, 乘法指令地址(文件偏移), 旧stride, 新stride)
SCALES = [
    ("招式名",         0x02B538, 8, 32),
    ("特性名",         0x09C6C2, 8, 32),
]


def main() -> int:
    rom = ROM_PATH.read_bytes()

    print("=== 2 的幂表：单条 lsls 改移位 ===")
    lines = [
        "; =============================================================================",
        "; 定长表 stride 放大（自动生成，勿手改）",
        "; 由 scripts/research/ruby/a2_gen_asm_patch.py 生成",
        ";",
        "; 只处理「stride 是 2 的幂」的表：改一条 lsls 的移位立即数即可。",
        "; 非 2 幂的表（属性名×5 / 道具名×40 / 图鉴分类名×28 / 装饰名×28）",
        "; 需要改乘法展开序列，见文件末尾的注释。",
        "; =============================================================================",
        "",
    ]

    ok = 0
    for name, insn_off, old_s, new_s in SCALES:
        old_shift = old_s.bit_length() - 1
        new_shift = new_s.bit_length() - 1
        if (1 << old_shift) != old_s or (1 << new_shift) != new_s:
            print(f"  {name}: 非 2 的幂，跳过")
            continue

        hw = struct.unpack_from("<H", rom, insn_off)[0]
        insns = list(md.disasm(rom[insn_off:insn_off + 2], insn_off))
        if not insns:
            print(f"  {name}: 无法反汇编 @0x{insn_off:X}")
            continue
        ins = insns[0]
        print(f"  {name}: 0x{insn_off + GBA_BASE:08X}  "
              f"{ins.mnemonic} {ins.op_str}")

        if ins.mnemonic not in ("lsls", "lsl"):
            print(f"    ⚠️ 不是 lsls，跳过")
            continue

        # 解析 lsls rd, rs, #imm
        parts = [p.strip() for p in ins.op_str.split(",")]
        if len(parts) != 3 or not parts[2].startswith("#"):
            print(f"    ⚠️ 操作数形态不符，跳过")
            continue
        rd = int(parts[0].lstrip("r"))
        rs = int(parts[1].lstrip("r"))

        # 生成新指令
        new_hw = (new_shift << 6) | (rs << 3) | rd
        new_bytes = struct.pack("<H", new_hw)

        # 验证新指令反汇编正确
        chk = list(md.disasm(new_bytes, insn_off))
        if chk:
            print(f"    新指令: {chk[0].mnemonic} {chk[0].op_str}")

        lines.append(f"; stride ×{old_s} → ×{new_s}")
        lines.append(f".org 0x{insn_off + GBA_BASE:08X}")
        lines.append(f"    lsls r{rd}, r{rs}, #{new_shift}")
        lines.append("")
        ok += 1

    lines += [
        "; =============================================================================",
        "; 以下 4 张表 stride 非 2 的幂，不能靠单条移位改：",
        ";",
        ";   属性名        ×5   = lsls #2 + adds",
        ";   道具名        ×40  = lsls #2 + adds + lsls #3",
        ";   图鉴分类名    ×28  = lsls #3 + subs + lsls #2",
        ";   秘密基地装饰名 ×28  = 同上 + adds #0x14",
        ";",
        "; 改法选项：",
        ";   A. 改乘法展开序列（改 2~3 条指令，需精确验证）",
        ";   B. 换成「读指针数组」（重写整段，风险更高）",
        ";   C. 换 stride 到 2 的幂（如 ×28 → ×32，但要确认语义等价）",
        ";",
        "; 待定，见 docs/research/A26_REDO.md",
        "; =============================================================================",
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print()
    print(f"生成 {ok} 条 patch → {OUT}")
    print()
    print("=== 生成的 asm ===")
    print("\n".join(lines[:40]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
