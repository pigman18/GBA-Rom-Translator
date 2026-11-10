#!/usr/bin/env python3
"""非 2 的幂 stride：用绝对跳转 trampoline 在新区分段重算乘法。

## 为什么需要 trarpoline（实测 2026-11-04）

属性名 stride=5、特性说明 stride=19，都不是 2 的幂。它们的乘法是
**复合展开式**，只改一个移位立即数得不到目标 stride：

    属性名 5 → 20：
        0x02B6AC  lsls r1, r0, #2     ; 4i
        0x02B6AE  adds r1, r1, r0     ; 5i
        0x02B6B0  ldr  r0, [pc, #0x3c] ; 基址
        0x02B6B2  adds r1, r1, r0     ; base + 5i
      把 #2 改成 #4 只会得到 16i+1i = 17i，不是 20i。

    特性说明 19 → 38：
        19i = ((4i + i) << 2) - i
      把中间的 #2 改成 #3 得 40i - i = 39i，不是 38i。

原地也没有插入指令的空间（前后都是必需指令）。

## 做法

原位 8 字节（原来的 lsls+adds+ldr+adds）：

    0xXXXXXX: ldr r2, [pc, #0]   ; 读桩地址（基址 = (off+4)&~3）
    0xXXXXXX+2: bx r2            ; 跳过去
    0xXXXXXX+4: <桩地址 u32>     ; 字面量

桩（新区，4 字节对齐）：

    lsls r1, r0, #4        ; 16i       （属性名）
    lsls r2, r0, #2        ; 4i
    adds r1, r1, r2        ; 20i
    ldr  r2, [pc, #N]      ; 基址
    adds r1, r1, r2        ; base + 20i
    ldr  r2, [pc, #M]      ; 回来地址
    bx   r2                ; 跳回原位后续
    <基址 u32>
    <回来地址 u32>

## 为什么用 ldr pc + bx 而不是 b/bl

- `b` 只有 ±2KB 范围，实测 4 个站点周围 2KB 内**没有空洞**（全是代码）。
- `bl` 会覆盖 lr，若这段代码在函数中间会破坏返回地址。
- `ldr pc` + `bx` 用绝对地址，范围不限，且不动 lr/栈。

用法：
    python scripts/research/ruby/trampoline_non_pow2.py --dry-run
    python scripts/research/ruby/trampoline_non_pow2.py --write
"""
from __future__ import annotations

import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

GBA = 0x08000000
ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"

# 新区起点（32MB ROM 尾部空白区；现有产物最大到 0x02000000 左右）
STUB_AREA = 0x01F00000     # 文件偏移


# ---------------------------------------------------------------------------
# Thumb 编码
# ---------------------------------------------------------------------------
def t_ldr_lit(rd: int, at: int, lit: int, *, allow_placeholder: bool = False) -> bytes:
    base = (at + 4) & ~3
    delta = lit - base
    if allow_placeholder:
        return struct.pack("<H", 0x4800 | (rd << 8))
    if delta < 0 or delta % 4 or delta // 4 > 255:
        raise ValueError(f"ldr 字面量不可达 at=0x{at:06X} lit=0x{lit:06X}")
    return struct.pack("<H", 0x4800 | (rd << 8) | (delta // 4))


def t_bx(rm: int) -> bytes:
    return struct.pack("<H", 0x4700 | (rm << 3))


def t_lsls(rd: int, rs: int, imm: int) -> bytes:
    return struct.pack("<H", (imm << 6) | (rs << 3) | rd)


def t_adds_reg(rd: int, rs: int, rn: int) -> bytes:
    return struct.pack("<H", 0x1800 | (rn << 6) | (rs << 3) | rd)


# ---------------------------------------------------------------------------
# 站点定义
# ---------------------------------------------------------------------------
@dataclass
class Site:
    name: str
    replace_off: int      # 文件偏移：原位 8 字节起点
    resume_off: int       # 文件偏移：计算完跳回的位置
    base_addr: int        # 表基址（GBA）
    idx_reg: int          # 索引寄存器
    out_reg: int          # 结果寄存器（存 base+stride*i）
    old_stride: int
    new_stride: int
    add_base: bool = True
    note: str = ""
    stub_off: int = 0
    stub: bytes = b""
    site_patch: bytes = b""


def build_shift_terms(stride: int) -> list[tuple[int, int]]:
    """把 stride 拆成 (移位量, 系数) 列表，用移位+加法凑出来。

    返回 [(shift, mult), ...]，表示 sum(mult * (i << shift))。
    优先用 2 的幂组合。
    """
    terms: list[tuple[int, int]] = []
    remain = stride
    base_shift = 0
    # 提取公共的 2 的幂因子
    while remain and remain % 2 == 0:
        remain //= 2
        base_shift += 1
    # 把奇数部分二进制拆解
    bit = 0
    while remain:
        if remain & 1:
            terms.append((base_shift + bit, 1))
        remain >>= 1
        bit += 1
    return terms


def build_stub(s: Site) -> bytes:
    """生成 trampoline 桩。"""
    terms = build_shift_terms(s.new_stride)
    code = bytearray()
    at = s.stub_off

    # 第一项直接用 out_reg
    first_shift, _ = terms[0]
    code += t_lsls(s.out_reg, s.idx_reg, first_shift)
    at += 2

    # 其余项累加到 out_reg（用 scratch = out_reg 之外的临时寄存器）
    scratch = 3 if s.out_reg != 3 else 7
    for shift, _mult in terms[1:]:
        code += t_lsls(scratch, s.idx_reg, shift)
        at += 2
        code += t_adds_reg(s.out_reg, s.out_reg, scratch)
        at += 2

    # 加基址（add_base=False 时跳过：由原位代码负责）
    ldr_pos = None
    lit_base_at = None
    if s.add_base:
        code += t_ldr_lit(scratch, at, 0, allow_placeholder=True)
        ldr_pos = len(code) - 2
        at += 2
        code += t_adds_reg(s.out_reg, s.out_reg, scratch)
        at += 2

    # 跳回：ldr scratch, [pc] ; bx scratch
    code += t_ldr_lit(scratch, at, 0, allow_placeholder=True)
    ldr_back_pos = len(code) - 2
    at += 2
    code += t_bx(scratch)
    at += 2

    # 对齐到 4
    while len(code) % 4:
        code += b"\x00\x00"

    # 基址字面量（add_base=False 时不放）
    lit_base = None
    if s.add_base:
        lit_base = s.stub_off + len(code)
        code += struct.pack("<I", s.base_addr)
    # 回来地址字面量
    lit_back = s.stub_off + len(code)
    code += struct.pack("<I", s.resume_off + GBA)

    # 回填 ldr 偏移
    def fix(pos: int, at_off: int, lit_off: int) -> None:
        delta = lit_off - ((at_off + 4) & ~3)
        assert delta >= 0 and delta % 4 == 0 and delta // 4 <= 255, \
            f"桩内 ldr 越界 delta={delta}"
        code[pos:pos + 2] = struct.pack("<H", 0x4800 | (scratch << 8) | (delta // 4))

    if ldr_pos is not None and lit_base is not None:
        fix(ldr_pos, s.stub_off + ldr_pos, lit_base)
    fix(ldr_back_pos, s.stub_off + ldr_back_pos, lit_back)
    return bytes(code)


def build_site_patch(s: Site) -> bytes:
    """原位 8 字节：ldr r2,[pc,#delta] ; bx r2 ; <stub 地址>。

    ⚠️ 字面量位置必须是 (replace_off + 4) & ~3，不能写死 replace_off + 4。
       实测 0x09C6D2（特性说明）：这一处不是 4 对齐，
       (0x09C6D2+4)&~3 = 0x09C6D4，字面量正好落在补丁的 +2 处，
       delta=0 可读；若写死 +4 = 0x09C6D6，delta=-2 越界。
    """
    lit_at = (s.replace_off + 4) & ~3
    out = bytearray()
    # ldr r2,[pc,#(lit_at - ((off+4)&~3))] —— 两者相同，delta 恒为 0
    out += t_ldr_lit(2, s.replace_off, lit_at)
    out += t_bx(2)
    # 补齐到字面量位置
    while len(out) < (lit_at - s.replace_off):
        out += b"\x00\x00"
    out += struct.pack("<I", s.stub_off + GBA)
    assert len(out) == 8, len(out)
    return bytes(out)


SITES = [
    # 属性名 5→20，三处形态略有不同：
    #   0x02B6AC: lsls/adds/ldr/adds  → 桩内加基址，跳回 0x02B6B4
    #   0x11C9BC: lsls/adds/ldr/b     → b 跳到 0x11CAC8，
    #             那里 dds r1,r1,r0 负责加基址（0x11CAC8 是
    #             两条分支的共享汇合点：0x11CAC4 走 stride8，本路径走 stride5，
    #             所以不能动 0x11CAC8，桩只算 20i 后跳过去）
    #   0x12E650: lsls/adds/ldr/adds  → 桩内加基址，跳回 0x12E658
    Site("属性名@0x02B6AC", 0x02B6AC, 0x02B6B4, 0x081CBB0C, 0, 1, 5, 20,
         add_base=True, note="桩内加基址"),
    Site("属性名@0x11C9BC", 0x11C9BC, 0x11CAC8, 0x081CBB0C, 0, 1, 5, 20,
         add_base=False,
         note="0x11CAC8 为共享汇合点(加基址在那)，桩只算 20i"),
    Site("属性名@0x12E650", 0x12E650, 0x12E658, 0x081CBB0C, 0, 1, 5, 20,
         add_base=True, note="桩内加基址"),
    # 特性说明 19→38。原序列 19i = ((4i+i)<<2)-i（8 字节），
    # 基址在 0x09C6DC 由 dds r0,r0,r1 加，所以桩只算 38i。
    # 0x09C6D2 不是 4 对齐，但 ldr 基址按 (pc+4)&~3 算出正好是
    # 0x09C6D4，字面量 delta=0 可读，8 字节补丁覆盖 0x09C6D2..0x09C6D9。
    Site("特性说明@0x09C6D2", 0x09C6D2, 0x09C6DA, 0x081CBEB4, 4, 0, 19, 38,
         add_base=False,
         note="桩算 38i，跳回 0x09C6DA（基址在那里加）"),
]


def main() -> int:
    write = "--write" in sys.argv
    rom = bytearray(ROM.read_bytes())

    print("=" * 82)
    print(f"非 2 幂 stride trampoline  {'（写入）' if write else '（dry-run）'}")
    print("=" * 82)

    cursor = STUB_AREA
    for s in SITES:
        s.stub_off = cursor
        s.stub = build_stub(s)
        s.site_patch = build_site_patch(s)
        cursor += len(s.stub)
        cursor = (cursor + 3) & ~3

        terms = build_shift_terms(s.new_stride)
        expr = " + ".join(f"i<<{sh}" for sh, _ in terms)
        print(f"\n{s.name}  {s.old_stride}→{s.new_stride}  ({expr})")
        print(f"  原位 0x{s.replace_off:06X} (8B): {s.site_patch.hex(' ')}")
        print(f"  桩   0x{s.stub_off:06X} ({len(s.stub)}B)")
        print(f"  跳回 0x{s.resume_off:06X}")
        print(f"  桩字节: {s.stub.hex(' ')}")
        import capstone as _cs
        _md = _cs.Cs(_cs.CS_ARCH_ARM, _cs.CS_MODE_THUMB)
        for _i in _md.disasm(s.stub, 0x08000000 + s.stub_off):
            print(f"      0x{_i.address:08X}: {_i.bytes.hex(' '):<9} "
                  f"{_i.mnemonic:<7} {_i.op_str}")

        # 校验：原位原指令确实是预期的序列
        orig = rom[s.replace_off:s.replace_off + 8]
        print(f"  原位原字节: {orig.hex(' ')}")

    print()
    if not write:
        print(f"需要新区 {cursor - STUB_AREA} 字节（0x{STUB_AREA:06X}..0x{cursor:06X}）")
        print("dry-run 结束。")
        return 0
    print("写入逻辑待接入 armips。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
