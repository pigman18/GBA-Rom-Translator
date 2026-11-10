"""调研(282) 逐个反汇编 0x08006xxx 里引用 decode16 的函数，找出真正的小字绘制。

═══ 281 的教训 ═══
0x080062B4 的公式是 addr = 0x081CEDF4 + (code>>16) + (code>>4)*512。
但码位只有 0x0000..0x0AFF，code>>16 恒为 0，指向全 0 区 ⇒ 解出全空。
说明这个函数处理的是别的码空间，不是小字。

⇒ 必须**逐个看**那 25 个调用点，而不是挑一个猜。

本脚本：
 ① 列出全部 26 个 decode16 调用点
 ② 对每个调用点，反汇编其所在函数的前 40 条
 ③ 提取每个函数用的 PC 字面量（页表/缓冲/宽度输出）
 ④ 按「字面量组合」归类，找出像小字的那一组
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
DEC = 0x08002F5C


def rd32(a):
    o = a - BASE
    return struct.unpack_from('<I', zh, o)[0] if 0 <= o <= N - 4 else None


def build_callers(rom, target):
    out = []
    for off in range(0, len(rom) - 4, 2):
        hw1 = rom[off] | (rom[off + 1] << 8)
        if (hw1 & 0xF800) != 0xF000:
            continue
        hw2 = rom[off + 2] | (rom[off + 3] << 8)
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
        if t == target:
            out.append(BASE + off)
    return out


callers = build_callers(zh, DEC)
print(f"decode16 0x{DEC:08X} 调用点 {len(callers)} 个\n")

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)


def func_head(addr):
    o = addr - BASE
    for k in range(o, max(0, o - 0x400), -2):
        hw = struct.unpack_from('<H', zh, k)[0]
        if (hw & 0xFE00) == 0xB400 and (hw & 0x0100):
            return BASE + k
    return addr


def lits_of(start, ln):
    """提取一段里的 ldr/adr 字面量。"""
    out = []
    i = start - BASE
    end = i + ln
    addr = start
    while i < end:
        hw = struct.unpack_from('<H', zh, i)[0]
        if (hw & 0xF800) == 0x4800:
            tgt = ((addr + 4) & ~3) + (hw & 0xFF) * 4
            out.append(((hw >> 8) & 7, tgt, rd32(tgt)))
        i += 2
        addr += 2
    return out


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


# 按函数分组
groups = defaultdict(list)
for c in callers:
    groups[func_head(c)].append(c)

print("=" * 78)
print(f"按所在函数分组：{len(groups)} 个函数")
print("=" * 78)
for fs in sorted(groups):
    cs = groups[fs]
    print(f"\n函数 0x{fs:08X}  (decode16 调用 {len(cs)} 次: "
          f"{[hex(c) for c in cs[:4]]})")
    # 取整个函数（到下一个调用点之后 0x40）
    ln = min(max(cs) - fs + 0x40, 0x300)
    lits = lits_of(fs, ln)
    seen = set()
    for rd, tgt, v in lits:
        if tgt in seen:
            continue
        seen.add(tgt)
        o = tgt - BASE
        old = struct.unpack_from('<I', ja, o)[0] if 0 <= o <= len(ja) - 4 else None
        ch = " *" if v != old else ""
        print(f"    lit@0x{tgt:08X} = 0x{v:08X}  {tag(v)}{ch}")
