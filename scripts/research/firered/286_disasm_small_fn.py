"""调研(286) 完整反汇编 0x08005D00..0x08006120，找出 0x080060ED 所在函数。

═══ 285 的结果 ═══
用 0x081CEDF4 页表 + 0x080062B4 的公式（(code>>4)*512）解出来是
**日文假名**（あいうえおかきくけこ...）—— 那是原版自带的假名小字库，不是中文。

⇒ 中文小字走的是另一条路。

═══ 回到唯一的线索 ═══
配置表 0x08E25F60（汉化新增）：
    [-5] 0x08E25F4C = 0x080060ED    ← 小字取字形函数（汉化改）
    [-4] 0x08E25F50 = 0x08B74000    ← 页表（11 页，原版 100% FF）
    [-3] 0x08E25F54 = 0x08B6C000    ← 默认页
    [-2] 0x08E25F58 = 0x00000100
    [-1] 0x08E25F5C = 0x00000110
    [+0] 0x08E25F60 = 0x08002F5D    ← 解码
    [+2] 0x08E25F68 = 0x020228FC    ← 输出缓冲

我之前从 0x080060EC 开始反汇编，但那是函数**中间**（有往回跳的 b）。
必须从更前面找到真正的入口，完整看这个函数怎么算地址。

本脚本：
 ① 从 0x08005D00 起完整反汇编到 0x08006120
 ② 标注所有 push/pop（函数边界）、PC 字面量、bl 目标
 ③ 找出 0x080060ED 所在函数的完整逻辑
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

LO, HI = 0x08005D00, 0x08006120


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
    return ""


md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
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
            mk = " *汉化改"
        mark = ""
        # 函数边界
        if (hw & 0xFE00) == 0xB400 and (hw & 0x0100):
            mark = "  <<< push+lr 函数入口"
        if ins.mnemonic == "pop" and "pc" in ins.op_str:
            mark = "  <<< pop pc 函数出口"
        # 关键地址高亮
        if 0x080060E0 <= addr <= 0x08006100:
            mark += "  <<< 目标函数区"
        print(f"  0x{addr:08X}{mk:<10} {raw.hex():<9} "
              f"{ins.mnemonic:<8} {ins.op_str}{mark}")
        # PC 字面量
        if (hw & 0xF800) == 0x4800:
            rd = (hw >> 8) & 7
            tgt = ((addr + 4) & ~3) + (hw & 0xFF) * 4
            v = rd32(tgt)
            o = tgt - BASE
            old = struct.unpack_from('<I', ja, o)[0] if 0 <= o <= len(ja) - 4 else None
            ch = " *汉化改" if v != old else ""
            print(f"            -> r{rd} = [0x{tgt:08X}] = 0x{v:08X}"
                  f"{tag(v)}{ch}")
    i += n
    addr += n
