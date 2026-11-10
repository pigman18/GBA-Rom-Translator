#!/usr/bin/env python3
"""生成 armips 补丁：9 张定长表的 stride 改写 + 非 2 幂 trampoline。

产出：
    configs/POKEMON_RUBY_AXVJ00/hook/patches/table_stride_full.asm
    configs/POKEMON_RUBY_AXVJ00/hook/patches/table_trampoline.asm

依据（实测 2026-11-04）：
  - 158 个 stride 站点用 solve_site_auto 三档起点兜底，K 值 100% 正确
  - 树果名无站点（唯一的 ldr 是元数据访问，不该改）
  - 属性名(5)、特性说明(19) 是非 2 幂，用 trampoline

用法：
    python scripts/research/ruby/emit_stride_patches.py
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
sys.path.insert(0, str(ROOT / "src"))

GAME = "POKEMON_RUBY_AXVJ00"
ROM = ROOT / "roms" / "origin" / f"{GAME}.gba"
PATCH_DIR = ROOT / "configs" / GAME / "hook" / "patches"

GBA_BASE = 0x08000000
STUB_AREA = 0x01F00000

# (表名, 表基址, 旧stride, 新stride, 说明)
#
# ⚠️ 2026-11-05 修正：只保留**纯名字表**。
#    实测 `bag` 场景卡死（`[ERR] 输入回调停摆`）的根因是：道具名/图鉴分类名/
#    秘密基地装饰名/树果名 这 4 张是**结构体**，entry 内除名字外还有指针字段
#    （道具 +0x10 名字指针、+0x18 描述指针；图鉴分类 +0x14 指针）。
#    游戏按硬编码偏移读这些字段，stride 一放大，字段整体后移 ⇒ 读到
#    FF FF FF FF 当指针用 ⇒ 卡死。
#    判据与证据见 scripts/research/ruby/audit_table_meta.py。
TABLES = [
    ("招式名",         0x1CACFC, 8,  32, "改移位立即数"),
    ("特性名",         0x1CBC44, 8,  32, "改移位立即数"),
    ("宝可梦名",       0x1CA354, 6,  24, "改移位立即数"),
]

# 结构体表：stride 保持原值，不生成任何 stride 补丁
STRUCT_KEEP_STRIDE = [
    ("道具名",         0x39A648, 40),
    ("图鉴分类名",     0x38474C, 28),
    ("秘密基地装饰名", 0x3C2A44, 28),
    ("树果名",         0x3A1050, 28),
]

# 非 2 幂：走 trampoline
TRAMPOLINE_TABLES = [
    ("属性名",   0x1CBB0C, 5,  20),
    ("特性说明", 0x1CBEB4, 19, 48),
]

# 这 3 处是元数据访问（读到的是指针/字段，不是名字），不该改
EXCLUDE = {
    (0x3C2A44, 0x0FA1F2), (0x3C2A44, 0x0FA5F0),
    (0x3A1050, 0x04F812),
}

# trampoline 站点（手工确认过的跳回点与是否在桩内加基址）
TRAMPOLINE_SITES = [
    # (表, replace_off, resume_off, base_gba, idx_reg, out_reg, old, new, add_base, note)
    ("属性名@0x02B6AC", 0x02B6AC, 0x02B6B4, 0x081CBB0C, 0, 1, 5, 20, True,
     "桩内加基址"),
    ("属性名@0x11C9BC", 0x11C9BC, 0x11CAC8, 0x081CBB0C, 0, 1, 5, 20, False,
     "0x11CAC8 是共享汇合点(adds r1,r1,r0 在那)，桩只算 20i 后跳过去"),
    ("属性名@0x12E650", 0x12E650, 0x12E658, 0x081CBB0C, 0, 1, 5, 20, True,
     "桩内加基址"),
    ("特性说明@0x09C6D2", 0x09C6D2, 0x09C6DA, 0x081CBEB4, 4, 0, 19, 48, False,
     "桩算 48i，跳回 0x09C6DA（基址在那里由 adds r0,r0,r1 加）"),
]


# ---------------------------------------------------------------------------
# Thumb 编码
# ---------------------------------------------------------------------------
def t_ldr_lit(rd: int, at: int, lit: int, *, placeholder: bool = False) -> bytes:
    if placeholder:
        return struct.pack("<H", 0x4800 | (rd << 8))
    delta = lit - ((at + 4) & ~3)
    if delta < 0 or delta % 4 or delta // 4 > 255:
        raise ValueError(f"ldr 不可达 at=0x{at:06X} lit=0x{lit:06X}")
    return struct.pack("<H", 0x4800 | (rd << 8) | (delta // 4))


def t_bx(rm: int) -> bytes:
    return struct.pack("<H", 0x4700 | (rm << 3))


def t_lsls(rd: int, rs: int, imm: int) -> bytes:
    return struct.pack("<H", ((imm & 0x1F) << 6) | (rs << 3) | rd)


def t_adds_reg(rd: int, rs: int, rn: int) -> bytes:
    return struct.pack("<H", 0x1800 | (rn << 6) | (rs << 3) | rd)


def shift_terms(stride: int) -> list[int]:
    """stride 拆成 2 的幂之和，返回移位量列表。"""
    terms, remain, sh = [], stride, 0
    while remain and remain % 2 == 0:
        remain //= 2
        sh += 1
    bit = 0
    while remain:
        if remain & 1:
            terms.append(sh + bit)
        remain >>= 1
        bit += 1
    return terms


# ---------------------------------------------------------------------------
# asm 输出
# ---------------------------------------------------------------------------
def fmt_bytes(b: bytes) -> str:
    return ", ".join(f"0x{x:02X}" for x in b)


def emit_stride_asm(rom: bytes) -> tuple[str, int]:
    from meowth.table_stride import find_ldrs, plan_stride_rewrite

    lines = [
        "; =============================================================================",
        "; 定长表 stride 改写（2 的幂倍数）",
        ";",
        "; 由 scripts/research/ruby/emit_stride_patches.py 生成，勿手改。",
        "; 依据：solve_site_auto 三档起点兜底，158 个站点 K 值 100% 正确。",
        "; 每处只改一条 shift 指令的立即数，不改指令长度。",
        "; =============================================================================",
        "",
    ]
    total = 0
    for name, base, old_s, new_s, mode in TABLES:
        plan = plan_stride_rewrite(rom, base, old_s, new_s)
        lines.append(f"; ---- {name}  0x{base:06X}  stride {old_s} → {new_s}  "
                     f"({plan.n_patches} 处) ----")
        for pt in plan.patches:
            lines.append(f"; {pt.label}")
            lines.append(f".org 0x{pt.offset + GBA_BASE:08X}")
            lines.append(f"    .byte {fmt_bytes(pt.data)}")
            lines.append("")
            total += 1
        for s in plan.skipped:
            if (base, s.ldr_off) in EXCLUDE:
                lines.append(f"; 跳过 0x{s.ldr_off:06X}: 元数据访问"
                             f"（读到的是字段/指针，不是名字），不该改")
            else:
                lines.append(f"; ⚠️ 跳过 0x{s.ldr_off:06X}: K={s.stride} ({s.reason})")
        lines.append("")
    return "\n".join(lines), total


def emit_trampoline_asm(rom: bytes) -> tuple[str, int]:
    lines = [
        "; =============================================================================",
        "; 非 2 的幂 stride：绝对跳转 trampoline",
        ";",
        "; 由 scripts/research/ruby/emit_stride_patches.py 生成，勿手改。",
        ";",
        "; 为什么需要 trampoline：",
        ";   属性名 stride=5 → 20，特性说明 stride=19 → 38，都不是 2 的幂。",
        ";   它们的乘法是复合展开式，只改一个移位立即数得不到目标 stride：",
        ";     属性名 5 → 20： lsls #2(4i) + adds(+i) = 5i，改 #4 只得 17i",
        ";     特性说明 19 → 38： ((4i+i)<<2)-i，改 <<3 得 39i",
        ";   原地也没有插入指令的空间。",
        ";",
        "; 做法：原位 8 字节换成 `ldr r2,[pc]` + `bx r2` + 桩地址，",
        ";       桩放新区，算完后 bx 跳回。用 ldr+bx 而非 b/bl 的原因：",
        ";         `b` 只有 ±2KB（实测周围无空洞）；`bl` 会覆盖 lr。",
        "; =============================================================================",
        "",
    ]

    cursor = STUB_AREA
    total = 0
    for (name, rep, resume, base_gba, idx_r, out_r,
         old_s, new_s, add_base, note) in TRAMPOLINE_SITES:
        terms = shift_terms(new_s)
        expr = " + ".join(f"i<<{t}" for t in terms)
        scratch = 3 if out_r != 3 else 7

        # 桩代码
        code = bytearray()
        stub_off = cursor

        def at() -> int:
            return stub_off + len(code)

        code += t_lsls(out_r, idx_r, terms[0])
        for sh in terms[1:]:
            code += t_lsls(scratch, idx_r, sh)
            code += t_adds_reg(out_r, out_r, scratch)

        fixups: list[tuple[int, int]] = []
        ldr_pos = None
        if add_base:
            pos = len(code)
            code += t_ldr_lit(scratch, at(), 0, placeholder=True)
            fixups.append((pos, at()))
            ldr_pos = pos
            code += t_adds_reg(out_r, out_r, scratch)

        pos = len(code)
        code += t_ldr_lit(scratch, at(), 0, placeholder=True)
        fixups.append((pos, at()))
        code += t_bx(scratch)

        while len(code) % 4:
            code += b"\x00\x00"

        lits = []
        if add_base:
            lits.append((fixups[0], stub_off + len(code)))
            code += struct.pack("<I", base_gba)
        lits.append((fixups[-1], stub_off + len(code)))
        code += struct.pack("<I", resume + GBA_BASE)

        for (pos, at_off), lit_off in lits:
            delta = lit_off - ((at_off + 4) & ~3)
            assert delta >= 0 and delta % 4 == 0 and delta // 4 <= 255, \
                f"{name}: 桩内 ldr 越界"
            code[pos:pos + 2] = struct.pack(
                "<H", 0x4800 | (scratch << 8) | (delta // 4))

        # 原位补丁
        lit_at = (rep + 4) & ~3
        site = bytearray()
        site += t_ldr_lit(2, rep, lit_at)
        site += t_bx(2)
        while len(site) < (lit_at - rep):
            site += b"\x00\x00"
        site += struct.pack("<I", stub_off + GBA_BASE)
        assert len(site) == 8, len(site)

        lines.append(f"; ---- {name}  {old_s} → {new_s}   ({expr}) ----")
        lines.append(f"; {note}")
        lines.append(f"; 原位 0x{rep:06X} 原字节: {rom[rep:rep+8].hex(' ')}")
        lines.append(f"; 桩   0x{stub_off:06X}  跳回 0x{resume:06X}")
        lines.append(f".org 0x{rep + GBA_BASE:08X}")
        lines.append(f"    .byte {fmt_bytes(bytes(site))}")
        lines.append("")
        lines.append(f"; -- 桩体（放在 0x{stub_off + GBA_BASE:08X}）--")
        lines.append(f".org 0x{stub_off + GBA_BASE:08X}")
        lines.append(f"    .byte {fmt_bytes(bytes(code))}")
        lines.append("")

        cursor = (stub_off + len(code) + 3) & ~3
        total += len(code) + 8

    lines.append(f"; 新区占用 {cursor - STUB_AREA} 字节"
                 f"（0x{STUB_AREA:06X}..0x{cursor:06X}）")
    return "\n".join(lines), total


def main() -> int:
    rom = ROM.read_bytes()
    PATCH_DIR.mkdir(parents=True, exist_ok=True)

    stride_asm, n_stride = emit_stride_asm(rom)
    p1 = PATCH_DIR / "table_stride_full.asm"
    p1.write_text(stride_asm + "\n", encoding="utf-8")
    print(f"写出 {p1.name}: {n_stride} 处补丁")

    tramp_asm, n_tramp = emit_trampoline_asm(rom)
    p2 = PATCH_DIR / "table_trampoline.asm"
    p2.write_text(tramp_asm + "\n", encoding="utf-8")
    print(f"写出 {p2.name}: {len(TRAMPOLINE_SITES)} 个 trampoline"
          f"（{n_tramp} 字节）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
