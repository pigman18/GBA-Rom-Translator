"""找「字体配置表」的同构表 —— 小字应该有自己的配置。

═══ 251 的关键结构 ═══
0x089D1430..0x089D1448（一张字体配置表）：
    0x089D1430 = 0x00000AFF     码位上限
    0x089D1434 = 0x089D08A0     PAGES4（页表）
    0x089D1438 = 0x03003DE0     解码输出缓冲
    0x089D143C = 0x089D08D0     WIDTH（字宽表）
    0x089D1440 = 0x03003E60     宽高输出
    0x089D1444 = 0x081DB3EF     取字形函数
    0x089D1448 = 0x08002F5D     解码函数

  ← 这是「大字体」的完整配置！

⇒ 小字体必然也有一张同结构的表：
     码上限 / 页表 / 缓冲 / 字宽表 / 输出 / 取字形 / 解码

本脚本：全 ROM 搜「含 0x08002F5D（解码函数）的配置表」，
       以及「含 0x081DB3EF（取字形）的表」，逐张对比。
"""
from __future__ import annotations

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
BASE = 0x08000000
N = len(zh)


def rd32(a):
    o = a - BASE
    return struct.unpack_from('<I', zh, o)[0] if 0 <= o <= N - 4 else None


def desc(a):
    v = rd32(a)
    if v is None:
        return "?"
    s = f"0x{a:08X} = 0x{v:08X}"
    if BASE <= v < BASE + N:
        s += " ROM"
    elif 0x03000000 <= v < 0x04000000:
        s += " IWRAM"
    elif 0x02000000 <= v < 0x03000000:
        s += " EWRAM"
    return s


print("=" * 78)
print("① 全 ROM 搜解码函数 0x08002F5D 的引用")
print("=" * 78)
for pat, tag in ((struct.pack('<I', 0x08002F5D), "0x08002F5D"),
                 (struct.pack('<I', 0x08002F5C), "0x08002F5C")):
    pos = zh.find(pat)
    hits = []
    while pos >= 0:
        hits.append(BASE + pos)
        pos = zh.find(pat, pos + 1)
    print(f"  {tag}: {len(hits)} 处 -> {[hex(h) for h in hits]}")

print("\n" + "=" * 78)
print("② 每处引用前后 8 项（找同构的字体配置表）")
print("=" * 78)
pos = zh.find(struct.pack('<I', 0x08002F5C))
refs = []
while pos >= 0:
    refs.append(BASE + pos)
    pos = zh.find(struct.pack('<I', 0x08002F5C), pos + 1)

for ref in refs:
    print(f"\n  配置表 @0x{ref:08X}:")
    for k in range(-7, 3):
        a = ref + k * 4
        star = " <<<解码" if k == 0 else ""
        print(f"    [{k:+2d}] {desc(a)}{star}")

print("\n" + "=" * 78)
print("③ 全 ROM 搜取字形函数 0x081DB3EF 的引用（已知 3 处）")
print("=" * 78)
pos = zh.find(struct.pack('<I', 0x081DB3EF))
refs2 = []
while pos >= 0:
    refs2.append(BASE + pos)
    pos = zh.find(struct.pack('<I', 0x081DB3EF), pos + 1)
for ref in refs2:
    print(f"\n  表 @0x{ref:08X}:")
    for k in range(-7, 3):
        a = ref + k * 4
        star = " <<<取字形" if k == 0 else ""
        print(f"    [{k:+2d}] {desc(a)}{star}")

print("\n" + "=" * 78)
print("④ 搜「另一个 WIDTH 表」：已知主 WIDTH @0x089D08D0，值只有 0A/0C")
print("=" * 78)
# 小字宽=8，所以小字 WIDTH 表应该全是 0x08
needle = bytes([8]) * 32
pos = zh.find(needle)
hits = []
while pos >= 0:
    hits.append(BASE + pos)
    pos = zh.find(needle, pos + 1)
print(f"  连续 32 个 0x08 的位置: {len(hits)} 处 -> {[hex(h) for h in hits[:12]]}")

# 找「值为 0x08 的 256+ 字节表」
best = []
for off in range(0, N - 256, 4):
    seg = zh[off:off + 256]
    n8 = sum(1 for b in seg if b == 8)
    if n8 > 200:
        best.append((n8, BASE + off))
best.sort(reverse=True)
print(f"\n  256 字节中 0x08 超过 200 个的表: {len(best)} 处，前 10:")
for n8, a in best[:10]:
    print(f"    0x{a:08X}: {n8}/256 个 0x08")

# 原版是否有对应
print("\n=== 这些位置在原版的情况 ===")
for n8, a in best[:6]:
    o = a - BASE
    jn = sum(1 for b in ja[o:o + 256] if b == 8)
    jff = sum(1 for b in ja[o:o + 256] if b == 0xFF)
    print(f"  0x{a:08X}: 汉化 {n8}/256 个 0x08  原版 {jn}/256 个 0x08, FF={jff}")
