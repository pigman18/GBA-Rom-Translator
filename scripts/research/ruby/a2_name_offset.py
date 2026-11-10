#!/usr/bin/env python3
"""用反汇编读出的「字段偏移」，确定 6 张表的 name_offset 与可用宽度。

关键洞察：
  index×stride 之后，代码会 `adds rX, #导偏移` 或直接 `ldr [rX, #off]`。
  那个偏移量就是字段位置 —— 这是唯一可靠的来源。

已读到的偏移：
  秘密基地装饰名 0x0AF2D8: adds r2, #0x14   ← 名字在 +0x14 = 20
  其余表的偏移需要继续跟随后续指令。

本脚本对每张表：
  1. 反汇编 index×stride 之后的 40 字节
  2. 找第一个「对结果 rX 的固定偏移加/读」
  3. 输出该偏移 = name_offset

用法：
    python scripts/research/ruby/a2_name_offset.py
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

# (表名, base, stride, ldr位置)
TABLES = [
    ("招式名",         0x1CACFC, 8,  0x02B53A),
    ("特性名",         0x1CBC44, 8,  0x09C6C4),
    ("属性名",         0x1CBB0C, 5,  0x02B6B0),
    ("道具名",         0x39A648, 40, 0x0A538E),
    ("图鉴分类名",     0x38474C, 28, 0x08C1D6),
    ("秘密基地装饰名", 0x3C2A44, 28, 0x0AF2C8),
]


def main() -> int:
    rom = ROM_PATH.read_bytes()

    for name, base, stride, ldr in TABLES:
        print(f"\n{'=' * 72}")
        print(f"=== {name}  stride={stride}  ldr@0x{ldr:X} ===")

        # 从 ldr 往后看 48 字节
        code = rom[ldr:ldr + 48]
        found_off = None
        base_reg = None
        acc_reg = None

        for ins in md.disasm(code, ldr):
            m, o = ins.mnemonic, ins.op_str
            parts = [p.strip() for p in o.split(",")]

            # 记录 ldr 的目标寄存器（加载 base）
            if ins.address == ldr and m == "ldr" and parts:
                base_reg = parts[0]

            # adds rX, rY, #imm  ← 可能是加 base 或加字段偏移
            if m in ("adds", "add") and len(parts) == 3 and parts[2].startswith("#"):
                imm = parts[2]
                if parts[1] == base_reg:
                    # 加 base（索引完成），下一处 imm 才是字段偏移
                    pass
                elif acc_reg and parts[1] == acc_reg:
                    # 累加寄存器 + 立即数 = 字段偏移
                    try:
                        found_off = int(imm[1:], 0)
                    except ValueError:
                        pass

            # ldr/ldrb/ldrh rX, [rY, #imm]  ← 直接读字段
            if m in ("ldr", "ldrb", "ldrh") and len(parts) == 2:
                mem = parts[1]
                if "#" in mem:
                    try:
                        imm = int(mem.split("#")[1].rstrip("]"), 0)
                        if found_off is None:
                            found_off = imm
                    except ValueError:
                        pass
                # 记录被读的基寄存器
                if "[" in mem:
                    acc_reg = mem.strip("[]").split(",")[0].strip()

            # adds rX, rY, rZ（寄存器相加，可能是加 base）
            if m in ("adds", "add") and len(parts) == 3 and not parts[2].startswith("#"):
                acc_reg = parts[0]

            mark = ""
            if found_off is not None and ("#" in o):
                mark = f"   [字段偏移候选 +0x{found_off:X}]"
            print(f"  0x{ins.address:06X}: {m:<8}{o}{mark}")

            if ins.address - ldr > 40:
                break

        # 结论
        print()
        if found_off is not None:
            print(f"  ⇒ name_offset ≈ +0x{found_off:X} ({found_off})")
            usable = stride - found_off
            print(f"  ⇒ 名字可用宽度 ≈ {usable}B")
        else:
            print(f"  ⇒ 未能自动识别偏移，需人工看")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
