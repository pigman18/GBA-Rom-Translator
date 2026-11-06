"""定长表指针修改（流水线模块）。

对应 docs/ALGO_TABLE_EXPAND.md 阶段 3。

两种形态：
  A. patch_literal   —— 改 ldr rX,[pc,#n] 指向的 u32 字面量
  B. patch_dispatch  —— 改 index×stride 的乘法常量 + 基址常量

设计原则：
  - 只产出 patch 列表，不直接改 ROM（调用方决定何时应用）
  - 所有校验（对齐、越界、原值是否匹配）都在这里做完
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

GBA_BASE = 0x08000000


@dataclass
class AsmPatch:
    """要写进 hook/patches/*.asm 的指令改动。

    参考 patches/pokedex.asm 的做法：
        .org 0x0808AA00
            mov r1, DEX_NAME_COLUMN

    这里只记录「改哪里、改成什么」，由 generate_asm_patches() 汇总成文件。
    """

    offset: int          # GBA 地址（含 0x08000000）
    bytes_: bytes        # 新指令字节
    comment: str = ""

    def to_asm(self, origin: int, remain: int = 0) -> str:
        """渲染成 armips 的 .org + .byte 形式。

        `origin` 是本 patch 在 asm 文件里被 .org 的起始地址，
        用于计算实际要写的地址（offset - origin 决定跳过多少字节）。
        """
        skip = self.offset - origin
        lines = []
        if skip > 0:
            lines.append(f"    .skip {skip}")
        lines.append(f"    .byte " + ", ".join(f"0x{b:02X}" for b in self.bytes_)
                     + (f"    ; {self.comment}" if self.comment else ""))
        return "\n".join(lines)


def thumb_lsls_imm(rd: int, rs: int, shift: int) -> bytes:
    """生成 thumb `lsls rd, rs, #imm` 指令字节。

    编码: 000 00 iiiii sss ddd（0x0000 基 + imm<<6 + rs<<3 + rd）
    """
    if not (0 <= shift <= 31):
        raise ValueError(f"shift 超出范围: {shift}")
    hw = (shift << 6) | (rs << 3) | rd
    return struct.pack("<H", hw)


def make_stride_scale_patch(
    insn_off: int,
    old_shift: int,
    new_shift: int,
    rd: int,
    rs: int,
    label: str = "",
) -> AsmPatch:
    """生成「改移位立即数」的 patch（stride 从 2^old 放大到 2^new）。

    例：招式名 stride 8(2^3) → 32(2^5)
        make_stride_scale_patch(0x0802B538, 3, 5, rd=1, rs=1)
    """
    data = thumb_lsls_imm(rd, rs, new_shift)
    return AsmPatch(
        offset=insn_off,
        bytes_=data,
        comment=f"{label} lsls #{old_shift}→#{new_shift}"
                f" (stride ×{1 << old_shift}→×{1 << new_shift})",
    )


def generate_asm_patches(
    patches: list[AsmPatch],
    *,
    header: str = "",
    merge_gap: int = 16,
) -> str:
    """把多个 AsmPatch 汇总成一个 .asm 文件内容。

    相邻（间隔 ≤ merge_gap）的 patch 会合并到同一个 .org 块里，
    减少 .org 次数，也便于人工核对。
    """
    if not patches:
        return header

    ps = sorted(patches, key=lambda p: p.offset)
    lines = [header.rstrip()] if header else []
    lines.append("")

    group: list[AsmPatch] = []
    groups: list[list[AsmPatch]] = []

    for p in ps:
        if not group:
            group = [p]
            continue
        prev = group[-1]
        gap = p.offset - (prev.offset + len(prev.bytes_))
        if gap <= merge_gap:
            group.append(p)
        else:
            groups.append(group)
            group = [p]
    if group:
        groups.append(group)

    for g in groups:
        origin = g[0].offset
        lines.append(f".org 0x{origin:08X}")
        cursor = origin
        for p in g:
            if p.offset > cursor:
                lines.append(f"    .skip {p.offset - cursor}")
                cursor = p.offset
            body = ", ".join(f"0x{b:02X}" for b in p.bytes_)
            cmt = f"    ; {p.comment}" if p.comment else ""
            lines.append(f"    .byte {body}{cmt}")
            cursor += len(p.bytes_)
        lines.append("")

    return "\n".join(lines)


def parse_ldr_literal_target(rom: bytes, ldr_off: int) -> int | None:
    """解析一条 thumb `ldr rX,[pc,#imm]` 指令，返回它指向的字面量文件偏移。"""
    if ldr_off + 2 > len(rom):
        return None
    hw = struct.unpack_from("<H", rom, ldr_off)[0]
    if (hw & 0xF800) != 0x4800:
        return None
    imm = (hw & 0xFF) * 4
    return ((ldr_off + 4) & ~3) + imm


def find_ldr_for(rom: bytes, lit_off: int, back: int = 4096) -> list[int]:
    """找所有引用字面量 `lit_off` 的 thumb `ldr rX,[pc,#imm]`。"""
    out: list[int] = []
    lo = max(0, lit_off - back)
    for off in range(lo, lit_off, 2):
        hw = struct.unpack_from("<H", rom, off)[0]
        if (hw & 0xF800) != 0x4800:
            continue
        imm = (hw & 0xFF) * 4
        if ((off + 4) & ~3) + imm == lit_off:
            out.append(off)
    return out


@dataclass
class Patch:
    """一条待应用的字节修改。"""

    offset: int      # 文件偏移
    data: bytes
    label: str = ""

    def __len__(self) -> int:
        return len(self.data)

    def __repr__(self) -> str:
        return (f"Patch(0x{self.offset:06X}, {self.data.hex(' ')}"
                + (f", {self.label})" if self.label else ")"))


# ---------------------------------------------------------------------------
# 形态 A：改字面量
# ---------------------------------------------------------------------------
def find_ldr_literals(rom: bytes, lit_off: int, back: int = 4096) -> list[int]:
    """找所有引用字面量 `lit_off` 的 thumb `ldr rX,[pc,#imm]` 指令偏移。

    Thumb 编码: 01001 Rt IIIIIIII（0x4800 掩码），
    目标 = ((insn_addr + 4) & ~3) + imm * 4
    """
    out: list[int] = []
    lo = max(0, lit_off - back)
    for off in range(lo, lit_off, 2):
        hw = struct.unpack_from("<H", rom, off)[0]
        if (hw & 0xF800) != 0x4800:
            continue
        imm = (hw & 0xFF) * 4
        if ((off + 4) & ~3) + imm == lit_off:
            out.append(off)
    return out


def find_literal_sites(rom: bytes, gba_addr: int, *, require_aligned: bool = True) -> list[int]:
    """在全 ROM 找值为 `gba_addr` 的 u32 的位置。"""
    needle = struct.pack("<I", gba_addr)
    out: list[int] = []
    start = 0
    while True:
        i = rom.find(needle, start)
        if i < 0:
            break
        if not require_aligned or i % 4 == 0:
            out.append(i)
        start = i + 1
    return out


def patch_literal(
    rom: bytes,
    old_base: int,
    new_base: int,
    *,
    expect_ldr: bool = True,
    back: int = 4096,
) -> list[Patch]:
    """把指向 `old_base` 的字面量改成 `new_base`。

    两种站点都会处理：
      1. 被 ldr [pc] 引用的字面量（代码里 `ldr rX,=table`）
      2. 表内/脚本里的裸 u32 指针（对齐的）

    返回 patch 列表；`expect_ldr=True` 时要求至少有一个 ldr 站点，
    否则视为「定位失败」抛异常（防止悄悄改错地方）。

    参数里的 base 都是**文件偏移**，内部自动加 0x08000000。
    """
    if old_base == new_base:
        return []

    old_gba = GBA_BASE + old_base
    new_gba = GBA_BASE + new_base

    sites = find_literal_sites(rom, old_gba, require_aligned=True)
    if not sites:
        raise LookupError(
            f"找不到值为 0x{old_gba:08X} 的字面量，无法改指 0x{new_gba:08X}"
        )

    patches: list[Patch] = []
    ldr_hits = 0
    for s in sites:
        cur = struct.unpack_from("<I", rom, s)[0]
        if cur != old_gba:
            continue
        ldrs = find_ldr_literals(rom, s, back=back)
        if ldrs:
            ldr_hits += 1
        patches.append(
            Patch(s, struct.pack("<I", new_gba),
                  f"literal 0x{old_gba:08X}→0x{new_gba:08X}"
                  + (f" (ldr@0x{ldrs[0]:X})" if ldrs else " (裸指针)"))
        )

    if expect_ldr and ldr_hits == 0:
        raise LookupError(
            f"0x{old_gba:08X} 有 {len(patches)} 处字面量，但无一处被 ldr [pc] 引用；"
            f"请确认 this 表是否真的被代码直接加载（可能走 index×stride）"
        )
    return patches


# ---------------------------------------------------------------------------
# 形态 B：改 index×stride 的分发
# ---------------------------------------------------------------------------
@dataclass
class IndexDispatch:
    """一处 `index×stride + base` 的机器码现场。"""

    base_literal_off: int     # 基址字面量所在文件偏移
    base_value: int           # 该字面量当前值（GBA 地址）
    mul_insns: list[int]      # 参与乘法的指令偏移
    stride: int               # 实测得出的步长


# 常见的 stride 乘法展开模式（Thumb）
#   ×28: lsls #3 → subs → lsls #2
#   ×40: lsls #2 → adds → lsls #3
#   ×20: lsls #2 → adds → lsls #2
#   ×4 : lsls #2
#   ×8 : lsls #3
_MUL_PATTERNS = {
    (("lsls", 3), ("subs", None), ("lsls", 2)): 28,
    (("lsls", 2), ("adds", None), ("lsls", 3)): 40,
    (("lsls", 2), ("adds", None), ("lsls", 2)): 20,
}


def detect_stride_from_disasm(insns: list[tuple[str, int | None]]) -> int | None:
    """从指令序列（mnemonic, shift）检测乘法展开对应的步长。"""
    for i in range(len(insns) - 2):
        key = tuple(insns[i:i + 3])
        if key in _MUL_PATTERNS:
            return _MUL_PATTERNS[key]
    # 单条移位
    if len(insns) >= 1:
        m, sh = insns[0]
        if m in ("lsls", "lsl") and sh in (2, 3, 4):
            return 4 << (sh - 2) if sh >= 2 else None
    return None


def patch_dispatch_to_ptrarr(
    rom: bytes,
    dispatch: IndexDispatch,
    new_ptrarr_base: int,
) -> list[Patch]:
    """把 `index×stride + base` 改成 `index×4 + new_ptrarr_base`。

    ⚠️ 这一步要改机器码本身，风险高于改字面量。
    实现要点：
      1. 把乘法序列改成 ×4（`lsls rX, #2` 单条）
      2. 把基址字面量改成新指针数组地址

    当前实现**只改基址字面量**，并把乘法保留——
    这仅在 stride == 4 时正确（即新表就是 u32 指针数组且旧 stride==4）。
    其它情况抛 NotImplementedError，避免静默写错。
    """
    if dispatch.stride != 4:
        raise NotImplementedError(
            f"stride={dispatch.stride} 的机器码改写尚未实现；"
            f"请先用 expand_fixed 保持 stride，或手工确认乘法序列改写方案"
        )
    return [
        Patch(dispatch.base_literal_off,
              struct.pack("<I", GBA_BASE + new_ptrarr_base),
              f"dispatch base → ptrarr 0x{GBA_BASE + new_ptrarr_base:08X}")
    ]
