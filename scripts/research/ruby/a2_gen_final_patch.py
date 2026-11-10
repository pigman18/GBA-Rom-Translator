#!/usr/bin/env python3
"""生成 6 张表最终的 stride asm patch（定稿）。

用户决策（2026-11-04）：
  1. 属性名用方案 C：接受 ×17 当 stride，只改一条 lsls
  2. 秘密基地装饰名修正为 ×56（不是 ×112）

最终方案：
  | 表            | 指令地址     | 旧    | 新    | 新stride | 可用 | 最长译文 |
  |---------------|--------------|-------|-------|----------|------|----------|
  | 招式名        | 0x0802B538   | #3    | #5    | 32       | 32   | 21B ✓    |
  | 特性名        | 0x0809C6C2   | #3    | #5    | 32       | 32   | 17B ✓    |
  | 属性名        | 0x0802B6AC   | #2    | #4    | 17       | 17   | 13B ✓    |
  | 道具名        | 0x080A538C   | #3    | #4    | 80       | 49   | 29B ✓    |
  | 图鉴分类名    | 0x0808C1D4   | #2    | #3    | 56       | 34   | 17B ✓    |
  | 秘密基地装饰名 | 0x080AF2D6   | #2    | #3    | 56       | 38   | 29B ✓    |

属性名 ×17 的推导：
  原序列  lsls r1, r0, #2   → r1 = i*4
          adds r1, r1, r0   → r1 = i*4 + i = i*5
  改后    lsls r1, r0, #4   → r1 = i*16
          adds r1, r1, r0   → r1 = i*16 + i = i*17
  ⇒ stride 5 → 17，18 项 × 17B = 306 B，13B 译文放得下

用法：
    python scripts/research/ruby/a2_gen_final_patch.py
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
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
OUT = (ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook" / "patches"
       / "table_stride.asm")
GBA_BASE = 0x08000000

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

# (表名, 指令地址, 旧stride, 新stride, 新移位, 公式, 可用, 最长译文, 项数)
PATCHES = [
    ("招式名",         0x02B538, 8,       32, 5, "i<<3",        32, 21, 354),
    ("特性名",         0x09C6C2, 8,       32, 5, "i<<3",        32, 17, 77),
    ("属性名",         0x02B6AC, 5,       17, 4, "i*16+i",      17, 13, 18),
    ("道具名",         0x0A538C, 40,      80, 4, "(i*4+i)<<4",  49, 29, 348),
    ("图鉴分类名",     0x08C1D4, 28,      56, 3, "(i*8-i)<<3",  34, 17, 386),
    ("秘密基地装饰名", 0x0AF2D6, 28,      56, 3, "(i*8-i)<<3",  38, 29, 120),
]


def thumb_lsls(rd: int, rs: int, imm: int) -> bytes:
    return struct.pack("<H", (imm << 6) | (rs << 3) | rd)


def main() -> int:
    rom = ROM_PATH.read_bytes()

    lines = [
        "; " + "=" * 77,
        "; 定长表 stride 放大（自动生成，勿手改）",
        "; 生成器: scripts/research/ruby/a2_gen_final_patch.py",
        ";",
        "; 原理：index×stride 的 Thumb 展开，最后一条 lsls 决定 2 的幂因子。",
        ";       改该 lsls 的移位立即数即可放大 stride，不动指令长度。",
        ";",
        "; 配合 docs/ALGO_PIPELINE.md 的通用流水线使用。",
        "; " + "=" * 77,
        "",
    ]

    print(f"{'表':<16} {'地址':>12} {'原指令':>18} {'新指令':>18} "
          f"{'stride':>10} {'可用':>5} {'最长':>5}")
    print("-" * 92)

    ok = 0
    for name, off, old_s, new_s, new_imm, formula, usable, longest, n in PATCHES:
        insns = list(md.disasm(rom[off:off + 2], off))
        if not insns:
            print(f"  {name}: 反汇编失败 @0x{off:X}")
            continue
        ins = insns[0]
        parts = [p.strip() for p in ins.op_str.split(",")]
        if len(parts) != 3:
            print(f"  {name}: 操作数不符 {ins.op_str}")
            continue
        rd = int(parts[0].lstrip("r"))
        rs = int(parts[1].lstrip("r"))
        old_imm = int(parts[2][1:], 0) if parts[2].startswith('#') else 0

        new_bytes = thumb_lsls(rd, rs, new_imm)
        chk = list(md.disasm(new_bytes, off))
        chk_s = f"{chk[0].mnemonic} {chk[0].op_str}" if chk else "?"
        orig_s = f"{ins.mnemonic} {ins.op_str}"

        # 校验容量
        fit = "✓" if longest <= usable else "✗"
        print(f"{name:<16} 0x{off + GBA_BASE:08X} {orig_s:>18} {chk_s:>18} "
              f"{old_s:>4}→{new_s:<4} {usable:>5} {longest:>4}{fit}")

        lines.append(f"; {name}: stride {old_s} → {new_s}  公式 {formula}")
        lines.append(f";   可用 {usable}B，最长译文 {longest}B，{n} 项 × {new_s}B "
                     f"= {n * new_s:,}B")
        lines.append(f";   原 lsls r{rd}, r{rs}, #{old_imm} "
                     f"→ 新 lsls r{rd}, r{rs}, #{new_imm}")
        lines.append(f".org 0x{off + GBA_BASE:08X}")
        lines.append(f"    .byte 0x{new_bytes[0]:02X}, 0x{new_bytes[1]:02X}"
                     f"    ; lsls r{rd}, r{rs}, #{new_imm}")
        lines.append("")
        ok += 1

    lines.append("; " + "=" * 77)
    lines.append("; 属性名说明（stride 5 → 17）：")
    lines.append(";   原序列  lsls r1,r0,#2  → i*4")
    lines.append(";           adds r1,r1,r0  → i*4+i = i*5")
    lines.append(";   改后    lsls r1,r0,#4  → i*16")
    lines.append(";           adds r1,r1,r0  → i*16+i = i*17")
    lines.append(";   18 项 × 17B = 306B，13B 译文放得下。")
    lines.append("; " + "=" * 77)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print()
    print(f"生成 {ok} 条 patch → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
