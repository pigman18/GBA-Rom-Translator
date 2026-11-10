"""调研(244) 完整反汇编 0x081DB3EE —— PrintNextChar 的「另一条路径」。

═══ 为什么查它 ═══
0x089D13E0 (PrintNextChar) 有两个分支：
    cmp r1, #0
    bne 0x089D1426        ← r1 != 0 走这条
    ...
    cmp r0, #0xAFF
    bhi 0x089D1426        ← 码 > 0x0AFF 也走这条
  0x089D1426: bx [0x081DB3EF]

主字库（12x16）走的是**前半段**（0x089D13EE..）。
0x081DB3EE 这条分支**从未被完整分析过** —— 207 只看了前 20 条（取页基址那段）。

小字（8x8）很可能走这条。

本脚本：完整反汇编 0x081DB3EE..0x081DB4C0，逐条标注，
提取所有 PC 字面量，找出小字的页表/宽度表。
"""
from __future__ import annotations

import struct
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
BASE = 0x08000000

FN = 0x081DB3EE
END = 0x081DB4C0


def rd32(rom, a):
    o = a - BASE
    return struct.unpack_from('<I', rom, o)[0] if 0 <= o <= len(rom) - 4 else None


print("=" * 78)
print(f"完整反汇编 0x{FN:08X} .. 0x{END:08X}")
print("=" * 78)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
ins_list = []
for ins in md.disasm(zh[FN - BASE:END - BASE], FN):
    raw = zh[ins.address - BASE:ins.address - BASE + ins.size]
    o = ins.address - BASE
    mk = ""
    if o + 2 <= len(ja):
        old = struct.unpack_from('<H', ja, o)[0]
        if ins.size == 2:
            if struct.unpack_from('<H', raw)[0] != old:
                mk = " *汉化改"
        else:
            if (zh[o:o + 4] != ja[o:o + 4]):
                mk = " *汉化改"
    ins_list.append((ins.address, ins.mnemonic, ins.op_str, raw, mk))
    print(f"  0x{ins.address:08X}{mk:<10} {raw.hex():<9} "
          f"{ins.mnemonic:<8} {ins.op_str}")

# ── 提取 PC 字面量 ────────────────────────────────────────
print("\n" + "=" * 78)
print("PC 相对字面量（手工解码，capstone 的 mem.base 不可靠）")
print("=" * 78)
addr = FN
i = FN - BASE
end_i = END - BASE
while i < end_i:
    hw = zh[i] | (zh[i + 1] << 8)
    if (hw & 0xF800) == 0x4800:
        rd = (hw >> 8) & 7
        tgt = ((addr + 4) & ~3) + (hw & 0xFF) * 4
        val = rd32(zh, tgt)
        oval = rd32(ja, tgt)
        ch = " *汉化改" if val != oval else ""
        extra = ""
        if val is not None:
            if BASE <= val < BASE + len(zh):
                extra = " ROM"
            elif 0x03000000 <= val < 0x04000000:
                extra = " IWRAM"
            elif 0x02000000 <= val < 0x03000000:
                extra = " EWRAM"
        print(f"  0x{addr:08X}  ldr r{rd}, [pc]  -> lit@0x{tgt:08X} "
              f"= 0x{val:08X}  (原 0x{oval:08X}){extra}{ch}")
    elif (hw & 0xF800) == 0xA000:
        rd = (hw >> 8) & 7
        tgt = ((addr + 4) & ~3) + (hw & 0xFF) * 4
        val = rd32(zh, tgt)
        print(f"  0x{addr:08X}  adr r{rd}         -> 0x{tgt:08X} = 0x{val:08X}")
    i += 2
    addr += 2

# ── 关键：0x081DB3EE 附近是否还有别的表 ────────────────────
print("\n" + "=" * 78)
print("函数体内嵌的字面量池内容（0x081DB4A0..0x081DB4C0）")
print("=" * 78)
for a in range(0x081DB4A0, 0x081DB4C0, 4):
    v = rd32(zh, a)
    ov = rd32(ja, a)
    ch = " *汉化改" if v != ov else ""
    print(f"  0x{a:08X} = 0x{v:08X}  (原 0x{ov:08X}){ch}")

# ── 0x081DB74000 那张表（207 提到的备用页表）───────────────
print("\n" + "=" * 78)
print("备用页表 0x08B74000 的 11+ 项")
print("=" * 78)
for k in range(14):
    a = 0x08B74000 + k * 4
    v = rd32(zh, a)
    ov = rd32(ja, a)
    ch = " *汉化改" if v != ov else ""
    tag = ""
    if v is not None and BASE <= v < BASE + len(zh):
        oo = v - BASE
        nf = sum(1 for b in ja[oo:oo + 0x4000] if b == 0xFF)
        tag = f"  原版该 16KB 中 FF={nf}"
    print(f"  [{k:>2}] 0x{v:08X}  (原 0x{ov:08X}){ch}{tag}")
