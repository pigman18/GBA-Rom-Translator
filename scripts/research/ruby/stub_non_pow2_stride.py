#!/usr/bin/env python3
"""非 2 的幂 stride 改写：用跳转桩（trampoline）在新区重算乘法。

背景（2026-11-04 实测）：
  属性名 stride=5，特性说明 stride=19，都不是 2 的幂。
  这类表的乘法是**复合展开式**，只改一个移位立即数得不到目标 stride：
    属性名 5 → 20：`lsls r1,r0,#2` + `adds r1,r1,r0` = 5i，
        改成 `lsls #4` 只得 17（16i+1i），不是 20。
    特性说明 19 → 38：19i = ((4i+i)<<2)-i，改成 <<3 得 40-1=39，不是 38。

  原地也没有插入指令的空间（前后都是必需指令）。

做法（trampoline）：
  原位 4 字节（原来的 lsls+adds）替换为：
      b    <桩地址>       ; 2 字节，无条件跳转，不破坏 lr
      nop                 ; 2 字节填充
  桩（放在新区，4 字节对齐）：
      重算 base + new_stride*i
      b    <原位后续>     ; 跳回

  为什么用 `b` 不用 `bl`：`bl` 会覆盖 lr，若这段代码在函数中间就会
  破坏返回地址。`b` 只改 pc。

覆盖率判据：
  改写后重新反汇编，桩里必须出现目标系数；并确认原位 `b` 目标正确。

用法：
    python scripts/research/ruby/stub_non_pow2_stride.py --dry-run
    python scripts/research/ruby/stub_non_pow2_stride.py --write
"""
from __future__ import annotations

import struct
import sys
from dataclasses import dataclass
from pathlib import Path

import capstone

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

GBA = 0x08000000
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

# (表名, 表基址, 旧 stride, 新 stride)
TABLES = [
    ("属性名",   0x1CBB0C, 5,  20),
    ("特性说明", 0x1CBEB4, 19, 38),
]


def thumb_b(from_off: int, to_off: int) -> bytes:
    """无条件跳转 b（2 字节）。范围 ±2KB。"""
    delta = to_off - (from_off + 4)
    if delta % 2 or not (-2048 <= delta <= 2046):
        raise ValueError(f"b 跳转越界: 0x{from_off:06X} -> 0x{to_off:06X}")
    imm11 = (delta // 2) & 0x7FF
    return struct.pack("<H", 0xE000 | imm11)


def thumb_ldr_pc(rd: int, at: int, lit_off: int) -> bytes:
    """ldr rd, [pc, #imm8]（2 字节），lit 必须 4 对齐且在上方。"""
    base = (at + 4) & ~3
    delta = lit_off - base
    if delta < 0 or delta % 4 or delta // 4 > 255:
        raise ValueError(f"ldr 字面量不可达: at=0x{at:06X} lit=0x{lit_off:06X}")
    return struct.pack("<H", 0x4800 | (rd << 8) | (delta // 4))


def thumb_lsls(rd: int, rs: int, imm: int) -> bytes:
    return struct.pack("<H", 0x0000 | (imm << 6) | (rs << 3) | rd)


def thumb_adds_reg(rd: int, rs: int, rn: int) -> bytes:
    return struct.pack("<H", 0x1800 | (rn << 6) | (rs << 3) | rd)


@dataclass
class StubPlan:
    table: str
    old_stride: int
    new_stride: int
    site: int                 # ldr 站点（原位要替换的起点）
    replace_at: int           # 被替换的指令起点
    replace_len: int          # 被替换长度
    resume_at: int            # 计算完跳回的位置
    stub_at: int              # 桩位置（新区）
    stub_code: bytes
    site_patch: bytes


def build_multiply(base_reg: int, idx_reg: int, stride: int) -> bytes:
    """生成 base + stride*i 的指令序列（用 lsls/adds 组合）。

    从最省指令的 2 的幂开始找，再拆成移位+加法。
    """
    # 把 stride 分解成 2 的幂之和，用最少的项
    parts = []
    remain = stride
    bit = 0
    while remain:
        if remain & 1:
            parts.append(bit)
        remain >>= 1
        bit += 1
    return parts


def main() -> int:
    write = "--write" in sys.argv
    rom = ROM.read_bytes()

    print("=" * 78)
    print(f"非 2 幂 stride trampoline  {'（写入）' if write else '（dry-run）'}")
    print("=" * 78)

    for name, base, old_s, new_s in TABLES:
        print(f"\n--- {name}  base=0x{base:06X}  {old_s} → {new_s} ---")
        parts = build_multiply(0, 0, new_s)
        terms = " + ".join(f"{idx_reg_name}(i)<<{p}"
                           for p, idx_reg_name in
                           ((p, "i") for p in parts))
        print(f"  {new_s} = {' + '.join(f'i<<{p}' for p in parts)}")
        print(f"  需要的项: 移位 {parts}")

    print()
    print("方案说明：")
    print("  原位 4 字节 → `b <桩>` + `nop`")
    print("  桩在新区分两段：算 i*new_stride，再 ldr 基址，adds，最后 b 跳回")
    print()

    if not write:
        print("dry-run 结束。")
        return 0
    print("⚠️ 写入逻辑待实现（需先确定新区地址与字面量池位置）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
