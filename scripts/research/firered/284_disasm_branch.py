"""调研(284) 追 0x08006354 的分支逻辑 + 0x08002F9C 函数。

═══ 283 的关键 ═══
0x08006354 里：
    08006358  lsrs r6, r0, #0x10     r6 = code >> 16
    0800635A  cmp  r6, #0
    0800635C  bne  0x08006390        code>>16 != 0 -> 另一分支
    0800635E  movs r0, #2
    08006360  bl   0x08002F9C        调 0x08002F9C
    （decode16 在这里被调用 4 次）

⇒ 码位空间按 code>>16 分页。这与我之前只用 lo/hi 的假设不同。

本脚本：
 ① 反汇编 0x08006354 完整
 ② 反汇编 0x08002F9C
 ③ 反汇编 0x08006418 / 0x080064B8 / 0x0800657C（其余 4 次调用的）
 ④ 重点看每个函数里「宽/高 写入」的立即数，确定各自是几种字号
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
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)


def rd32(a):
    o = a - BASE
    return struct.unpack_from('<I', zh, o)[0] if 0 <= o <= N - 4 else None


def dis(start, ln, label):
    print("=" * 78)
    print(f"{label}  @0x{start:08X}")
    print("=" * 78)
    i = start - BASE
    end = min(i + ln, N)
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
                mk = " *"
            extra = ""
            # 标注 strb 立即数（宽高）
            if ins.mnemonic == "strb" and ins.op_str.startswith("r0, "):
                extra = "  <- 可能是宽/高"
            print(f"  0x{addr:08X}{mk:<2} {raw.hex():<9} "
                  f"{ins.mnemonic:<8} {ins.op_str}{extra}")
        i += n
        addr += n
    print()


dis(0x08006354, 0x110, "① 函数 0x08006354（4 次 decode16，含 code>>16 分支）")
dis(0x08002F9C, 0x40, "② 0x08002F9C")
dis(0x08006418, 0xB0, "③ 函数 0x08006418")
