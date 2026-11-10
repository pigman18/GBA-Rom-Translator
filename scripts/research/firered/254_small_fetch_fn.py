"""反汇编小字取字形函数 0x080060ED —— 拿到小字的地址公式。

═══ 253 的决定性发现 ═══
小字配置表 @0x08E25F60：
    [-5] 0x08E25F4C = 0x080060ED    ★小字取字形函数
    [-4] 0x08E25F50 = 0x08B74000    页表（11 项）
    [-3] 0x08E25F54 = 0x08B6C000    默认页
    [-2] 0x08E25F58 = 0x00000100    段偏移1
    [-1] 0x08E25F5C = 0x00000110    段偏移2
    [+0] 0x08E25F60 = 0x08002F5D    解码函数
    [+1] 0x08E25F64 = 0x081C7A89    另一函数
    [+2] 0x08E25F68 = 0x020228FC    输出缓冲

注意：页表 0x08B74000 与主字库**不同**（主用 0x089D08A0）。
⇒ 小字有自己的页表，但仍在原版 FF 区（11 页 × 16KB）。

本脚本：
 ① 反汇编 0x080060ED
 ② 反汇编 0x081C7A89
 ③ 按得出的公式导出小字字库
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


def rd32(a):
    o = a - BASE
    return struct.unpack_from('<I', zh, o)[0] if 0 <= o <= N - 4 else None


md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)


def dis(start, ln, label):
    print("=" * 78)
    print(f"{label}  0x{start:08X}")
    print("=" * 78)
    addr = start
    i = start - BASE
    end = i + ln
    while i < end:
        for ins in md.disasm(zh[i:i + 4], BASE + i):
            raw = zh[ins.address - BASE:ins.address - BASE + ins.size]
            o = ins.address - BASE
            mk = ""
            if o + ins.size <= len(ja) and zh[o:o + ins.size] != ja[o:o + ins.size]:
                mk = " *汉化改"
            print(f"  0x{ins.address:08X}{mk:<9} {raw.hex():<9} "
                  f"{ins.mnemonic:<8} {ins.op_str}")
            break
        hw = struct.unpack_from('<H', zh, i)[0]
        step = 2
        # Thumb-2 32-bit 指令粗判
        if (hw & 0xF800) in (0xF000, 0xF800, 0xE800):
            step = 4
        i += step
        addr += step
    print()


dis(0x080060ED & ~1, 0xC0, "① 小字取字形函数")
dis(0x081C7A89 & ~1, 0x80, "② 0x081C7A89")

print("=" * 78)
print("③ 小字页表 0x08B74000（11 项）与原版对比")
print("=" * 78)
for k in range(12):
    a = 0x08B74000 + k * 4
    v = rd32(a)
    o = a - BASE
    old = struct.unpack_from('<I', ja, o)[0]
    print(f"  [{k:>2}] 汉化 0x{v:08X}  原版 0x{old:08X}")

print("\n" + "=" * 78)
print("④ 小字默认页 0x08B6C000 的内容")
print("=" * 78)
o = 0x08B6C000 - BASE
for i in range(0, 0x80, 16):
    seg = zh[o + i:o + i + 16]
    jseg = ja[o + i:o + i + 16]
    mk = " *汉化改" if seg != jseg else ""
    print(f"  +{i:03X}  {seg.hex(' ')}{mk}")
