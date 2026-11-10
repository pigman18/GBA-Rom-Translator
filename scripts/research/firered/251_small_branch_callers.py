"""小字分支 0x081DB45C / 0x081DB47C 是独立函数 —— 找它们的调用者。

═══ 250 的关键认识 ═══
0x081DB3EE 主流程从 0x081DB3EE 一直执行到 0x081DB45A（pop），
中间**没有跳到 0x081DB45C 的分支**。

⇒ 0x081DB45C 和 0x081DB47C 是两个**独立函数入口**，
   只是紧邻主函数、共用字面量池。

本脚本：
 ① 找 0x081DB45C / 0x081DB47C 的函数指针引用（u32，带 bit0）
 ② 找 bl 到这两个地址的
 ③ 若有指针表，看表里还有什么
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

SMALL1 = 0x081DB45C
SMALL2 = 0x081DB47C
MAIN = 0x081DB3EE


def rd32(a):
    o = a - BASE
    return struct.unpack_from('<I', zh, o)[0] if 0 <= o <= len(zh) - 4 else None


print("=" * 78)
print("① 三个函数的指针引用（u32，含 Thumb bit0）")
print("=" * 78)
for name, addr in (("主 0x081DB3EE", MAIN), ("小1 0x081DB45C", SMALL1),
                   ("小2 0x081DB47C", SMALL2)):
    for tag, nd in (("|1", struct.pack('<I', addr | 1)),
                    ("  ", struct.pack('<I', addr))):
        pos = zh.find(nd)
        hits = []
        while pos >= 0:
            hits.append(BASE + pos)
            pos = zh.find(nd, pos + 1)
        if hits:
            print(f"  {name} {tag}: {len(hits)} 处 -> {[hex(h) for h in hits[:10]]}")

print("\n" + "=" * 78)
print("② bl 到这三个地址的调用点")
print("=" * 78)


def build_callers(rom):
    callers = defaultdict(list)
    N = len(rom)
    for off in range(0, N - 4, 2):
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
for name, addr in (("主", MAIN), ("小1", SMALL1), ("小2", SMALL2)):
    cs = callers.get(addr, [])
    print(f"  {name} 0x{addr:08X}: {len(cs)} 个 bl 调用 {[hex(c) for c in cs[:8]]}")

# ── 排在前面的那个指针表（3 处引用 0x081DB3EF）────────────────
print("\n" + "=" * 78)
print("③ 引用 0x081DB3EF 的三张表的完整内容")
print("=" * 78)
for ref in (0x08742148, 0x087C0190, 0x089D1444):
    o = ref - BASE
    print(f"\n  表 @0x{ref:08X} 前后 6 项:")
    for k in range(-3, 7):
        a = ref + k * 4
        v = rd32(a)
        ov = rd32(a - (0) )
        tag = ""
        if v is not None and BASE <= v < BASE + len(zh):
            tag = " ROM"
        elif v is not None and 0x03000000 <= v < 0x04000000:
            tag = " IWRAM"
        elif v is not None and 0x02000000 <= v < 0x03000000:
            tag = " EWRAM"
        star = " <<<" if k == 0 else ""
        print(f"    [{k:+2d}] 0x{a:08X} = 0x{v:08X}{tag}{star}")

# 这三张表附近是否有 0x081DB45D (小1|1)
print("\n" + "=" * 78)
print("④ 全 ROM 搜 0x081DB45D 和 0x081DB47D")
print("=" * 78)
for addr in (SMALL1 | 1, SMALL2 | 1, SMALL1, SMALL2):
    nd = struct.pack('<I', addr)
    pos = zh.find(nd)
    n = 0
    while pos >= 0:
        n += 1
        print(f"  0x{addr:08X} 引用 @0x{BASE + pos:08X}")
        pos = zh.find(nd, pos + 1)
    if n == 0:
        print(f"  0x{addr:08X}: 0 处")
