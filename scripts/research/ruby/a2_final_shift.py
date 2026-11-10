#!/usr/bin/env python3
"""最优解法：直接把乘法序列「最后一条 lsls」的移位量加 k。

原理：
  index×N 的 Thumb 展开，最后一步一定是 `lsls rX, rX, #m`。
  N = A × 2^m（A 是前面的加/减结果）。

  要把 stride 放大 2^k 倍，只需把这条 lsls 的 m 改成 m+k。

验证各表：
  属性名    ×5  = (i*4 + i) → 序列末尾无 lsls，需另看
  道具名    ×40 = (i*4+i) << 3     → lsls #3 → #4 即 ×80
  图鉴分类名 ×28 = (i*8-i) << 2    → lsls #2 → #3 即 ×56
  装饰名    ×28 = (i*8-i) << 2     → lsls #2 → #3 即 ×56（但需 ×4→#4 = ×112）

这是「改一个立即数」，比插入指令安全得多。

用法：
    python scripts/research/ruby/a2_final_shift.py
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
GBA_BASE = 0x08000000

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

# (表名, 乘法起点, 旧stride, 元数据, 需要可用)
TABLES = [
    ("属性名",         0x02B6AC, 5,  0,  16),
    ("道具名",         0x0A5388, 40, 31, 38),
    ("图鉴分类名",     0x08C1D0, 28, 22, 23),
    ("秘密基地装饰名", 0x0AF2D2, 28, 18, 39),
]


def parse_lsls(ins) -> tuple[int, int, int] | None:
    """解析 lsls rd, rs, #imm → (rd, rs, imm)"""
    parts = [p.strip() for p in ins.op_str.split(",")]
    if len(parts) != 3 or not parts[2].startswith("#"):
        return None
    try:
        rd = int(parts[0].lstrip("r"))
        rs = int(parts[1].lstrip("r"))
        imm = int(parts[2][1:], 0)
    except ValueError:
        return None
    return rd, rs, imm


def main() -> int:
    rom = ROM_PATH.read_bytes()
    out_lines = []

    print("=== 找每张表乘法序列「最后一条 lsls」===\n")

    for name, mul_off, old_s, meta, need in TABLES:
        print(f"--- {name}  旧stride={old_s} 元数据={meta} 需要可用≥{need} ---")
        code = rom[mul_off:mul_off + 20]
        insns = list(md.disasm(code, mul_off))

        last_lsls = None
        for ins in insns:
            if ins.mnemonic == "ldr" and "pc" in ins.op_str:
                break       # 到加载基址就停
            if ins.mnemonic in ("lsls", "lsl"):
                p = parse_lsls(ins)
                if p:
                    last_lsls = (ins.address, *p)
            print(f"    0x{ins.address:06X}: {ins.mnemonic:<8}{ins.op_str}")

        if last_lsls is None:
            print(f"  ❌ 序列里没有 lsls（纯 adds/subss 组合），需另想办法")
            print()
            continue

        addr, rd, rs, imm = last_lsls
        cur_stride = None

        # 计算当前 stride：如果前面只有 adds（×5 型），A=5；否则按移位
        # 简化：假设 old_s = A * 2^imm，求 A
        A = old_s >> imm if imm else old_s
        print(f"  最后 lsls @0x{addr:X}: r{rd}, r{rs}, #{imm}  "
              f"→ 等效 ×{A}×2^{imm} = ×{old_s}")

        # 目标 stride
        target = None
        for k in (1, 2, 3, 4):
            cand = old_s * (1 << k)
            if cand - meta >= need:
                target = (k, cand)
                break
        if target is None:
            print(f"  ❌ 放大到 ×16 仍不够")
            print()
            continue

        k, new_s = target
        new_imm = imm + k
        new_hw = (new_imm << 6) | (rs << 3) | rd
        new_bytes = struct.pack("<H", new_hw)
        chk = list(md.disasm(new_bytes, addr))

        print(f"  ⇒ 新 stride={new_s}（×{1 << k}）  新可用={new_s - meta}")
        print(f"  ⇒ 改 lsls #{imm} → #{new_imm}"
              + (f"（{chk[0].mnemonic} {chk[0].op_str}）" if chk else ""))
        print(f"  ⇒ patch: .org 0x{addr + GBA_BASE:08X}")

        out_lines.append(f"; {name}: stride ×{old_s} → ×{new_s}")
        out_lines.append(f".org 0x{addr + GBA_BASE:08X}")
        out_lines.append(f"    lsls r{rd}, r{rs}, #{new_imm}")
        out_lines.append("")
        print()

    if out_lines:
        print("=== 生成的 patch 片段 ===")
        print("\n".join(out_lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
