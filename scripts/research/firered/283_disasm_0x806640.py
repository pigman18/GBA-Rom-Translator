"""调研(283) 反汇编 0x08006640 —— 最像小字的那个（decode16 只调 2 次）。

═══ 282 的分组结果 ═══
8 个字体渲染函数。其中：
   0x080062B4  2 次  (页表 0x081CEDF4)
   0x08006304  2 次  (页表 0x081D2DF4)
   0x08006640  2 次  (页表 0x081EF13C)  ← 输出到 EWRAM 0x02021AC0
   其余 4-5 次

只调 2 次 = 两段 = 8x16，符合小字特征。
而且 0x08006640 还把结果写到了 EWRAM 0x02021AC0（与之前发现的
「小字缓冲在 EWRAM」吻合）。

本脚本反汇编 0x08006640 和 0x080062B4，逐条对照。
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
    print(f"{label}  @0x{start:08X}")
    print("=" * 78)
    i = start - BASE
    end = i + ln
    addr = start
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
                mk = " *汉化改"
            print(f"  0x{addr:08X}{mk:<9} {raw.hex():<9} "
                  f"{ins.mnemonic:<8} {ins.op_str}")
        i += n
        addr += n
    print()


dis(0x08006640, 0x100, "函数 A")
dis(0x080062B4, 0xB0, "函数 B（281 那个）")

# ── 页表内容 ────────────────────────────────────────────
print("=" * 78)
print("页表内容对比")
print("=" * 78)
for name, addr in (("A: 0x081EF13C", 0x081EF13C),
                   ("B: 0x081CEDF4", 0x081CEDF4),
                   ("C: 0x081DEDF4", 0x081DEDF4),
                   ("D: 0x081E6F0C", 0x081E6F0C)):
    print(f"\n{name}:")
    o = addr - BASE
    for i in range(0, 64, 16):
        seg = zh[o + i:o + i + 16]
        jseg = ja[o + i:o + i + 16]
        mk = " *汉化改" if seg != jseg else ""
        print(f"  0x{addr + i:08X}  {seg.hex(' ')}{mk}")
