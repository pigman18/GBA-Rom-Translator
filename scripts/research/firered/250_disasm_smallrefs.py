"""反汇编 0x081Bxxxx 一带 —— 小字缓冲的写入方。

═══ 249 的发现 ═══
0x02001F00 被这些 ROM 地址引用：
    0x081B19A9 / 0x081B488D / 0x081B881F / 0x083C16C5 / 0x08D07B74
0x02003D00 被 0x081BAD57 引用
0x02002800 被 0x081AC046 / 0x081AC0A2 / 0x081B491A / 0x081B492B ... 引用

⇒ 集中在 0x081Bxxxx，这是文本/字形模块。

本脚本反汇编这些引用点附近，找出小字真正的取用逻辑。
"""
from __future__ import annotations

import struct
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
BASE = 0x08000000

REFS = [0x081B19A9, 0x081B488D, 0x081B881F, 0x081BAD57, 0x081BBB51,
        0x081B491A, 0x081B4EF8, 0x081AC046]


def rd32(a):
    o = a - BASE
    return struct.unpack_from('<I', zh, o)[0] if 0 <= o <= len(zh) - 4 else None


md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

for ref in REFS:
    print("=" * 78)
    print(f"引用点 0x{ref:08X}")
    print("=" * 78)
    # 往前找函数头
    o = ref - BASE
    fs = None
    for k in range(o, max(0, o - 0x300), -2):
        hw = struct.unpack_from('<H', zh, k)[0]
        if (hw & 0xFE00) == 0xB400 and (hw & 0x0100):
            fs = BASE + k
            break
    print(f"  所在函数起点 ≈ 0x{fs:08X}" if fs else "  未找到函数头")
    start = fs if fs else ref - 0x40
    ln = min(ref - start + 0x40, 0x200)
    for ins in md.disasm(zh[start - BASE:start - BASE + ln], start):
        raw = zh[ins.address - BASE:ins.address - BASE + ins.size]
        oo = ins.address - BASE
        mk = ""
        if oo + 2 <= len(ja):
            old = struct.unpack_from('<H', ja, oo)[0]
            if ins.size == 2 and struct.unpack_from('<H', raw)[0] != old:
                mk = " *"
        hit = " <<<" if ins.address == ref else ""
        print(f"  0x{ins.address:08X}{mk:<2} {raw.hex():<9} "
              f"{ins.mnemonic:<8} {ins.op_str}{hit}")
    print()

# ── 关键：0x081B19A9 附近是否就是小字渲染 ─────────────────
print("=" * 78)
print("精读 0x081B1950..0x081B1A20")
print("=" * 78)
start = 0x081B1950
for ins in md.disasm(zh[start - BASE:0x081B1A20 - BASE], start):
    raw = zh[ins.address - BASE:ins.address - BASE + ins.size]
    print(f"  0x{ins.address:08X}  {raw.hex():<9} {ins.mnemonic:<8} {ins.op_str}")
    if ins.mnemonic == "ldr" and "[pc" in ins.op_str:
        hw = struct.unpack_from('<H', zh, ins.address - BASE)[0]
        if (hw & 0xF800) == 0x4800:
            tgt = ((ins.address + 4) & ~3) + (hw & 0xFF) * 4
            v = rd32(tgt)
            print(f"            -> lit@0x{tgt:08X} = 0x{v:08X}")
