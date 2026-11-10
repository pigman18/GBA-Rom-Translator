"""调研(287) 深挖 0x08006640 —— 完整反汇编 + 页表实态 + 调用者。

═══ 已知 ═══
函数 0x08006640（decode16 调 2 次，宽8 高0xC）：
    08006642  lsls r0, r0, #0x10
    08006644  lsrs r4, r0, #0x14       r4 = code >> 4
    08006646  lsls r4, r4, #9          (code>>4) * 512
    08006648  movs r1, #0xf0
    0800664A  lsls r1, r1, #0xc        r1 = 0xF0000
    0800664C  ands r1, r0              (code<<16) & 0xF0000
    0800664E  lsrs r1, r1, #0xc        = (code&0xF) << 4
    08006650  ldr  r0, [pc, #0x30]     → 0x08006688 = 0x03003DE0 ? 需核实
    08006652  adds r1, r1, r0
    08006654  adds r4, r4, r1          addr
    08006656  ldr  r5, [pc, #0x30]     → 第二个字面量
    0800665C  bl   0x08002F5C          段1
    08006660-64  r4 += 0x100
    0800666C  bl   0x08002F5C          段2
    08006674  movs r0, #8
    08006676  strb r0, [r1]            宽=8
    0800667A  movs r0, #0xc
    0800667C  strb r0, [r5,#0x81]      高=12

⚠ 关键：0x08006650 的字面量在 0x08006688，但 0x08006688 处的值是 0x03003DE0
   （283 dump 显示：08006688 = e0 3d 00 03）
   而 0x0800668C 起是另一段代码

   0x08006656 的字面量在 0x0800668C？但那是代码…
   ⇒ 需要重新精确算 PC 相对地址

本脚本：
 ① 精确解 0x08006640 函数的每个 PC 字面量（包括 PC 对齐）
 ② dump 每一个字面量的值
 ③ 找 0x08006640 的调用者
 ④ dump 页表和实际数据
"""
from __future__ import annotations

import struct
from collections import defaultdict
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
BASE = 0x08000000
N = len(zh)
FN = 0x08006640


def rd32(a):
    o = a - BASE
    return struct.unpack_from('<I', zh, o)[0] if 0 <= o <= N - 4 else None


def tag(v):
    if v is None:
        return "?"
    if BASE <= v < BASE + N:
        return "ROM"
    if 0x03000000 <= v < 0x04000000:
        return "IWRAM"
    if 0x02000000 <= v < 0x03000000:
        return "EWRAM"
    return ""


print("=" * 78)
print(f"① 精确解 {FN:#x} 的 PC 字面量（PC 对齐 = (addr+4) & ~3）")
print("=" * 78)
i = FN - BASE
end = i + 0x50
addr = FN
while i < end:
    hw = struct.unpack_from('<H', zh, i)[0]
    if (hw & 0xF800) == 0x4800:
        rd = (hw >> 8) & 7
        pc = (addr + 4) & ~3
        tgt = pc + (hw & 0xFF) * 4
        v = rd32(tgt)
        o = tgt - BASE
        old = struct.unpack_from('<I', ja, o)[0] if 0 <= o <= len(ja) - 4 else None
        ch = " *汉化改" if v != old else ""
        print(f"  0x{addr:08X}  ldr r{rd}, [pc, #{(hw & 0xFF) * 4:#x}]")
        print(f"      PC对齐=0x{pc:08X}  -> lit@0x{tgt:08X} = "
              f"0x{v:08X}  {tag(v)}{ch}")
    i += 2
    addr += 2

print("\n" + "=" * 78)
print("② 函数体附近 0x08006640..0x080066A0 原始字节")
print("=" * 78)
o = FN - BASE
for i in range(0, 0x60, 16):
    seg = zh[o + i:o + i + 16]
    jseg = ja[o + i:o + i + 16]
    mk = " *汉化改" if seg != jseg else ""
    print(f"  0x{FN + i:08X}  {seg.hex(' ')}{mk}")

print("\n" + "=" * 78)
print(f"③ 谁调用 0x{FN:08X}")
print("=" * 78)
callers = []
for off in range(0, N - 4, 2):
    hw1 = zh[off] | (zh[off + 1] << 8)
    if (hw1 & 0xF800) != 0xF000:
        continue
    hw2 = zh[off + 2] | (zh[off + 3] << 8)
    if (hw2 & 0xF800) != 0xF800:
        continue
    s = (hw1 >> 10) & 1
    imm10 = hw1 & 0x03FF
    j1 = (hw2 >> 13) & 1
    j2 = (hw2 >> 11) & 1
    imm11 = hw2 & 0x07FF
    i1 = 1 - (j1 ^ s)
    i2 = 1 - (j2 ^ s)
    val = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
    if s:
        val -= (1 << 25)
    t = (BASE + off + 4 + val) & 0xFFFFFFFF
    if t == FN:
        callers.append(BASE + off)
print(f"  bl 调用 {len(callers)} 个: {[hex(c) for c in callers[:10]]}")

# 函数指针
for pat, nm in ((struct.pack('<I', FN), 'FN'), (struct.pack('<I', FN | 1), 'FN|1')):
    pos = zh.find(pat)
    hits = []
    while pos >= 0:
        hits.append(BASE + pos)
        pos = zh.find(pat, pos + 1)
    print(f"  {nm} 指针引用 {len(hits)} 处: {[hex(h) for h in hits[:10]]}")

print("\n" + "=" * 78)
print("④ 页表 0x081EF13C 及更大范围的实际数据")
print("=" * 78)
for base in (0x081EF13C, 0x081EF024, 0x081EF024 - 0x100):
    o = base - BASE
    if o < 0 or o + 64 > N:
        continue
    print(f"\n  0x{base:08X}:")
    for i in range(0, 64, 16):
        seg = zh[o + i:o + i + 16]
        jseg = ja[o + i:o + i + 16]
        mk = " *汉化改" if seg != jseg else ""
        print(f"    0x{base + i:08X}  {seg.hex(' ')}{mk}")

# 关键：整个 0x081E0000..0x081F0000 区域，哪里「原版 FF 或空、汉化有内容」
print("\n" + "=" * 78)
print("⑤ 0x081C0000..0x08200000 里，汉化新增数据的分布")
print("=" * 78)
W = 0x1000
for off in range(0x081C0000 - BASE, 0x08200000 - BASE, W):
    if off + W > N:
        break
    seg = zh[off:off + W]
    jseg = ja[off:off + W]
    added = sum(1 for a, b in zip(seg, jseg) if b == 0xFF and a != 0xFF)
    if added > 200:
        print(f"  0x{BASE + off:08X}: 新增 {added}/{W} ({added / W:.0%})")
