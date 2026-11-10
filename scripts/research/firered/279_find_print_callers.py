"""调研(279) 从队伍界面出发，找到真正的文字绘制入口。

═══ 大字是怎么追成的（207 的路径）═══
1. 已知「继续游戏」菜单的 DISPCNT/BG0CNT
2. 找到每帧执行的绘制分发函数 0x08000C34
3. 从中找到字符转码 0x081DB660、字宽 0x081DB630
4. 顺藤摸到 PrintNextChar 0x089D13E0 → 页表 0x089D08A0 → decode16

═══ 小字要重走同样的路，但入口不同 ═══
队伍界面 DISPCNT = 0x1740（已实测）
需要：
 ① 找到「队伍界面」这个 state 的更新函数
 ② 它的文字绘制调用点
 ③ 顺下去找小字的页表

【本脚本第一步】找 PrintNextChar 0x089D13E0 的**调用者**
 之前 251 查过 0x081DB3EF 的引用（3 处表），但没查 0x089D13E0 本身的调用者。
 PrintNextChar 是绘制单个字的函数，队伍界面的每个字都要调它。
 它的调用者就是「文字打印循环」。
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


def rd32(a):
    o = a - BASE
    return struct.unpack_from('<I', zh, o)[0] if 0 <= o <= N - 4 else None


def build_callers(rom):
    callers = defaultdict(list)
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
        callers[(BASE + off + 4 + val) & 0xFFFFFFFF].append(BASE + off)
    return callers


callers = build_callers(zh)

TARGETS = {
    "PrintNextChar 0x089D13E0": 0x089D13E0,
    "取字形 0x081DB3EE": 0x081DB3EE,
    "解码 0x08002F5C": 0x08002F5C,
    "字宽 0x081DB630": 0x081DB630,
}
for name, addr in TARGETS.items():
    cs = callers.get(addr, [])
    print(f"{name}: {len(cs)} 个 bl/bl 调用")
    for c in cs[:10]:
        print(f"    0x{c:08X}")
    print()

# ── 关键：找「按字符串连续打印」的循环 ────────────────────
# PrintNextChar 的调用者应该在一个循环里（每字一次）
print("=" * 78)
print("PrintNextChar 调用者所在的函数")
print("=" * 78)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
for c in callers.get(0x089D13E0, [])[:6]:
    o = c - BASE
    fs = None
    for k in range(o, max(0, o - 0x400), -2):
        hw = struct.unpack_from('<H', zh, k)[0]
        if (hw & 0xFE00) == 0xB400 and (hw & 0x0100):
            fs = BASE + k
            break
    print(f"\n调用点 0x{c:08X}  所在函数起点 ≈ "
          f"{'0x%08X' % fs if fs else '未找到'}")
    if fs:
        ln = min(c - fs + 0x40, 0x300)
        for ins in md.disasm(zh[fs - BASE:fs - BASE + ln], fs):
            raw = zh[ins.address - BASE:ins.address - BASE + ins.size]
            oo = ins.address - BASE
            mk = ""
            if oo + ins.size <= len(ja) and zh[oo:oo + ins.size] != ja[oo:oo + ins.size]:
                mk = " *"
            hit = " <<<" if ins.address == c else ""
            print(f"  0x{ins.address:08X}{mk:<2} {raw.hex():<9} "
                  f"{ins.mnemonic:<8} {ins.op_str}{hit}")
