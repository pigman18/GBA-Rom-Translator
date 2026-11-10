#!/usr/bin/env python3
"""非 2 幂表的解法：找「步长倍数」关系，而不是硬改乘法序列。

观察各表的 stride 与需求：
  表             旧stride  最长译文  需要
  属性名           5        13B      ≥16
  道具名          40        29B      ≥38
  图鉴分类名      28        17B      ≥23
  秘密基地装饰名   28        29B      ≥39

关键洞察：
  **stride 倍数关系**比绝对值重要。
  Thumb 的 index×N 常用移位+加减组合：
    ×28 = lsls#3 + subs + lsls#2   ← (i*8 - i)*4
    ×40 = lsls#2 + adds + lsls#3   ← (i*4 + i)*8
    ×5  = lsls#2 + adds            ← i*4 + i
    ×20 = lsls#2 + adds + lsls#2

  **若新 stride 是旧 stride 的 2 的幂倍数，只需在乘法序列末尾加一条 lsls。**
    例：图鉴 28 → 56 = 28×2，末尾加 `lsls #1`
        道具 40 → 80 = 40×2，末尾加 `lsls #1`
        属性  5 → 20 =  5×4，末尾加 `lsls #2`

  这比改乘法展开序列安全得多 —— 只是在结果上多移一位！

验证：在乘法之后、加基址之前插入一条 lsls。

用法：
    python scripts/research/ruby/a2_pow2_multiple.py
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

# (表名, 旧stride, 需要的最小可用, 现有可用, 乘法指令起点)
TABLES = [
    ("属性名",         5,  16, 5,  0x02B6AC),
    ("道具名",         40, 38, 9,  0x0A5388),
    ("图鉴分类名",     28, 23, 6,  0x08C1D0),
    ("秘密基地装饰名", 28, 39, 10, 0x0AF2D2),
]


def main() -> int:
    rom = ROM_PATH.read_bytes()

    print("=== 分析：能否靠「末尾追加移位」放大 stride ===\n")

    for name, old_s, need, usable, mul_off in TABLES:
        meta = old_s - usable     # 元数据字节数
        print(f"--- {name} ---")
        print(f"  旧 stride={old_s}  可用={usable}  元数据={meta}  "
              f"需要可用≥{need}")

        # 找满足 need 的最小 2 的幂倍数
        chosen = None
        for k in (1, 2, 4, 8):
            new_s = old_s * k
            new_usable = new_s - meta
            if new_usable >= need:
                chosen = (k, new_s, new_usable)
                break

        if chosen is None:
            print(f"  ❌ ×8 仍不够，需 VARLEN")
            print()
            continue

        k, new_s, new_usable = chosen
        print(f"  ⇒ 新 stride={new_s}（×{k}）  新可用={new_usable}")

        if k == 1:
            print(f"  ✅ 无需放大（旧 stride 已够）")
            print()
            continue

        # 反汇编乘法序列，找「加法完成、即将加基址」的位置
        print(f"  乘法序列 @0x{mul_off:X}:")
        code = rom[mul_off:mul_off + 24]
        insns = list(md.disasm(code, mul_off))
        insert_before = None
        base_ldr = None
        for ins in insns[:8]:
            mark = ""
            if ins.mnemonic in ("lsls", "lsl", "subs", "subs", "adds"):
                mark = "  [乘法]"
            if ins.mnemonic == "ldr" and "pc" in ins.op_str:
                mark = "  ← 加载基址"
                if insert_before is None:
                    insert_before = ins.address
            print(f"    0x{ins.address:06X}: {ins.mnemonic:<8}{ins.op_str}{mark}")
            if ins.address - mul_off > 16:
                break

        if insert_before is not None:
            print(f"  ⇒ 在 0x{insert_before:X} 之前插入 lsls #"
                  f"{k.bit_length() - 1}，等效 ×{k}")
            print(f"  ⚠️ 但插入指令会挤占后续字节，需确认那里有 nop 空间")
            # 检查插入点前是否有 nop
            prev = rom[insert_before - 2:insert_before]
            if prev == b"\xc0\x46":      # nop
                print(f"     ✅ 前一条是 nop，可直接替换")
            else:
                print(f"     ⚠️ 前一条不是 nop（{prev.hex()}），需另找空间")
        print()

    print("=== 结论 ===")
    print("  若乘法序列末尾（加基址之前）有 nop 空间，")
    print("  追加一条 lsls 就能放大 2 的幂倍数，比改乘法展开安全。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
