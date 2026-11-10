"""解剖 0x08E25F60 —— 小字的字体配置表。

═══ 252 的决定性发现 ═══
解码函数 0x08002F5D 全 ROM 只有 3 处引用：
    0x081DB4BC  ← 0x081DB3EE 内的 thunk（主字库分支用）
    0x089D1448  ← 主字库配置表
    0x08E25F60  ← ★第三处，从未看过！

主字库配置表 @0x089D1444 的结构（已确证）：
    -5] 0x00000AFF   码位上限
    -4] 0x089D08A0   PAGES4 页表
    -3] 0x03003DE0   解码输出缓冲
    -2] 0x089D08D0   WIDTH 字宽表
    -1] 0x03003E60   宽高输出
    +0] 0x081DB3EF   取字形函数
    +1] 0x08002F5D   解码函数

⇒ 0x08E25F60 附近应该有一张同构的小字配置表。

本脚本 dump 那一片，按结构逐项对照。
"""
from __future__ import annotations

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
BASE = 0x08000000
N = len(zh)

DEC = 0x08E25F60


def rd32(a):
    o = a - BASE
    return struct.unpack_from('<I', zh, o)[0] if 0 <= o <= N - 4 else None


def tag_of(v):
    if v is None:
        return ""
    if BASE <= v < BASE + N:
        return " ROM"
    if 0x03000000 <= v < 0x04000000:
        return " IWRAM"
    if 0x02000000 <= v < 0x03000000:
        return " EWRAM"
    if 0x04000000 <= v < 0x05000000:
        return " IO"
    if 0x05000000 <= v < 0x06000000:
        return " PAL"
    if 0x06000000 <= v < 0x07000000:
        return " VRAM"
    return ""


print("=" * 78)
print(f"① 配置表 @0x{DEC:08X} 前后 20 项")
print("=" * 78)
for k in range(-12, 10):
    a = DEC + k * 4
    v = rd32(a)
    ov = rd32(a)
    o = a - BASE
    old = struct.unpack_from('<I', ja, o)[0] if 0 <= o <= len(ja) - 4 else None
    ch = " *汉化改" if v != old else ""
    star = " <<<解码" if k == 0 else ""
    print(f"  [{k:+3d}] 0x{a:08X} = 0x{v:08X}{tag_of(v)}{ch}{star}")

print("\n" + "=" * 78)
print("② 与主字库配置表逐项对照")
print("=" * 78)
MAIN_TBL = 0x089D1444
print(f"  {'主字库 0x089D1444':<34} {'第三张 0x08E25F60':<34} 说明")
labels = ["-5 码位上限", "-4 页表", "-3 解码缓冲", "-2 字宽表",
          "-1 宽高输出", "+0 取字形", "+1 解码函数"]
for i, lab in enumerate(labels):
    k = i - 5
    a1 = MAIN_TBL + k * 4
    a2 = DEC + k * 4
    v1 = rd32(a1)
    v2 = rd32(a2)
    print(f"  {lab:<12} 0x{v1:08X}{tag_of(v1):<8} 0x{v2:08X}{tag_of(v2):<8}")

print("\n" + "=" * 78)
print("③ 若 -4 项是页表，dump 它")
print("=" * 78)
PAGES = rd32(DEC - 4 * 4)
print(f"  推测页表: 0x{PAGES:08X}" if PAGES else "  无")
if PAGES and BASE <= PAGES < BASE + N:
    for k in range(16):
        a = PAGES + k * 4
        v = rd32(a)
        o = v - BASE if v and BASE <= v < BASE + N else -1
        nf = sum(1 for b in ja[o:o + 0x4000] if b == 0xFF) if o >= 0 else -1
        print(f"    [{k:>2}] 0x{a:08X} = 0x{v:08X}   原版该16KB中FF={nf}")

print("\n" + "=" * 78)
print("④ 若 -2 项是字宽表，dump 前 64 项")
print("=" * 78)
WID = rd32(DEC - 2 * 4)
print(f"  推测字宽表: 0x{WID:08X}" if WID else "  无")
if WID and BASE <= WID < BASE + N:
    o = WID - BASE
    seg = zh[o:o + 64]
    print(f"  前 64 字节: {seg.hex(' ')}")
    from collections import Counter
    print(f"  值分布: {dict(Counter(seg).most_common(8))}")

print("\n" + "=" * 78)
print("⑤ 若 -3 项是解码缓冲（IWRAM），检查它")
print("=" * 78)
BUF = rd32(DEC - 3 * 4)
print(f"  推测解码缓冲: 0x{BUF:08X}" if BUF else "  无")

# ── 检查 0x08E25F60 周边是否是代码 ────────────────────────
print("\n" + "=" * 78)
print("⑥ 0x08E25F00..0x08E26000 原始字节")
print("=" * 78)
o = 0x08E25F00 - BASE
for i in range(0, 0x100, 16):
    seg = zh[o + i:o + i + 16]
    mark = "  ←配置表" if 0x08E25F60 - BASE == o + i else ""
    print(f"  0x{0x08E25F00 + i:08X}  {seg.hex(' ')}{mark}")
