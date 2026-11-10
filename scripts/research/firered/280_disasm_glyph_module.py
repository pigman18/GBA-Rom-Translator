"""调研(280) 反汇编字形绘制模块 0x08006200..0x08006600。

═══ 279 的关键发现 ═══
解码函数 0x08002F5C 有 26 个调用点，其中 25 个集中在 0x080062xx。
⇒ 这是真正的字形绘制模块，之前只看了 0x081DB3EE 那一个调用者。

本脚本完整反汇编这一段，提取全部 PC 字面量。
"""
from __future__ import annotations

import struct
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
BASE = 0x08000000
N = len(zh)

LO, HI = 0x08006200, 0x08006600


def rd32(a):
    o = a - BASE
    return struct.unpack_from('<I', zh, o)[0] if 0 <= o <= N - 4 else None


def tag(v):
    if v is None:
        return ""
    if BASE <= v < BASE + N:
        return " ROM"
    if 0x03000000 <= v < 0x04000000:
        return " IWRAM"
    if 0x02000000 <= v < 0x03000000:
        return " EWRAM"
    if 0x05000000 <= v < 0x06000000:
        return " PAL"
    if 0x06000000 <= v < 0x07000000:
        return " VRAM"
    if 0x04000000 <= v < 0x05000000:
        return " IO"
    return ""


md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
lits = []
print("=" * 78)
print(f"反汇编 0x{LO:08X} .. 0x{HI:08X}")
print("=" * 78)
i = LO - BASE
end = HI - BASE
addr = LO
while i < end:
    hw = struct.unpack_from('<H', zh, i)[0]
    n = 4 if (hw & 0xF800) in (0xF000, 0xF800, 0xE800) else 2
    if i + n > end:
        break
    got = list(md.disasm(zh[i:i + n], addr))
    if got:
        ins = got[0]
        raw = zh[i:i + n]
        mk = ""
        if i + n <= len(ja) and zh[i:i + n] != ja[i:i + n]:
            mk = " *"
        print(f"  0x{addr:08X}{mk:<2} {raw.hex():<9} "
              f"{ins.mnemonic:<8} {ins.op_str}")
    if (hw & 0xF800) == 0x4800:
        rd = (hw >> 8) & 7
        tgt = ((addr + 4) & ~3) + (hw & 0xFF) * 4
        lits.append((addr, f"ldr r{rd}", tgt, rd32(tgt)))
    elif (hw & 0xF800) == 0xA000:
        rd = (hw >> 8) & 7
        tgt = ((addr + 4) & ~3) + (hw & 0xFF) * 4
        lits.append((addr, f"adr r{rd}", tgt, rd32(tgt)))
    i += n
    addr += n

print("\n" + "=" * 78)
print("PC 字面量（去重）")
print("=" * 78)
seen = set()
for a, ins, tgt, v in lits:
    if tgt in seen:
        continue
    seen.add(tgt)
    o = tgt - BASE
    old = struct.unpack_from('<I', ja, o)[0] if 0 <= o <= len(ja) - 4 else None
    ch = " *汉化改" if v != old else ""
    print(f"  0x{a:08X}  {ins:<8} lit@0x{tgt:08X} = 0x{v:08X}"
          f"{tag(v)}{ch}")

print("\n" + "=" * 78)
print("其中的 ROM 指针")
print("=" * 78)
for a, ins, tgt, v in lits:
    if v is None or not (BASE <= v < BASE + N):
        continue
    o = v - BASE
    nf = sum(1 for b in ja[o:o + 0x100] if b == 0xFF)
    print(f"  0x{a:08X} -> 0x{v:08X}  原版该 256B 中 FF={nf}")
    print(f"      {zh[o:o + 32].hex(' ')}")
