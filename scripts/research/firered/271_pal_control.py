"""确认 decode16 用的 PAL 到底是不是 0x03000A40（IWRAM 运行时表）。

═══ 疑点 ═══
用小字页表 + PAL261 解出的 2452 字，像素值只有 1/2/3，
且分布是 137141 : 92330 : 84385 —— 背景只占 44%，不像正常字模（应 85%+）。

⇒ PAL 可能用错了。

【验证思路】
大字导出成功（207），用的是 PAL205（runtime205 快照）。
那次像素值分布是什么？如果也是三色且背景占比低，说明这是正常的；
如果背景占 85%+，说明小字这次的 PAL 有问题。

本脚本：
 ① 用同一逻辑重算大字，统计像素分布（对照组）
 ② 对比小字
 ③ 若差异大，尝试其他 PAL 来源
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
BASE = 0x08000000
N = len(zh)

IW205 = (ROOT / "work/_probe/runtime205/t000_prove_iwram.bin").read_bytes()
IW261 = (ROOT / "work/_probe/party261/s01_party01_iwram.bin").read_bytes()
PAL205 = IW205[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]
PAL261 = IW261[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]
IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]

PAGES_MAIN = [0x089C4230, 0x089555A0, 0x08B55564, 0x08A2725C, 0x08B333A0,
              0x08907C0C, 0x08AD690C, 0x08935A08, 0x08A72610, 0x08AB5404,
              0x089B2B0C]
PAGES_SMALL = [0x08B01000, 0x08B40000, 0x08B50000, 0x08B60000, 0x08B70000,
               0x08B80000, 0x08B90000, 0x08BA0000, 0x08BB0000,
               0x08B64000, 0x08B68000]


def decode16(src, pal):
    out = bytearray()
    for r3 in range(16):
        p = (r3 // 2) * 2
        v = src[p] if (r3 & 1) else (src[p + 1] if p + 1 < len(src) else 0)
        i = IDX[v]
        off = i * 2
        out += pal[off:off + 2] if off + 1 < len(pal) else b'\x00\x00'
    return bytes(out)


def mat8(b):
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = b[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


print("=" * 78)
print("① 对照组：大字（207 的成功逻辑）像素分布")
print("=" * 78)
vals = Counter()
bg_frac = []
for code in range(0, 512):
    hi, lo = code >> 8, code & 0xFF
    o = PAGES_MAIN[hi] + lo * 64 - BASE
    if o < 0 or o + 64 > N:
        continue
    segs = [mat8(decode16(zh[o + k * 16:o + k * 16 + 16], PAL205))
            for k in range(4)]
    m = np.vstack([np.hstack([segs[0], segs[1]]),
                   np.hstack([segs[2], segs[3]])])
    c = Counter(int(v) for v in m.flatten())
    for v, n in c.items():
        vals[v] += n
    bg = c.most_common(1)[0][0]
    bg_frac.append(c[bg] / m.size)
print(f"  值分布: {dict(sorted(vals.items()))}")
print(f"  背景占比: 平均 {np.mean(bg_frac):.1%}")

print("\n" + "=" * 78)
print("② 小字（PAL261）像素分布")
print("=" * 78)
vals2 = Counter()
bg_frac2 = []
for code in range(0, 512):
    hi, lo = code >> 8, code & 0xFF
    o = PAGES_SMALL[hi] + lo * 64 - BASE
    if o < 0 or o + 64 > N:
        continue
    o1 = o + 0x100
    if o1 + 16 > N:
        continue
    m = np.vstack([mat8(decode16(zh[o:o + 16], PAL261)),
                   mat8(decode16(zh[o1:o1 + 16], PAL261))])
    c = Counter(int(v) for v in m.flatten())
    for v, n in c.items():
        vals2[v] += n
    bg = c.most_common(1)[0][0]
    bg_frac2.append(c[bg] / m.size)
print(f"  值分布: {dict(sorted(vals2.items()))}")
print(f"  背景占比: 平均 {np.mean(bg_frac2):.1%}")

print("\n" + "=" * 78)
print("③ 交叉实验：4 种 PAL 组合")
print("=" * 78)
combos = [
    ("小字页 + PAL261", PAGES_SMALL, PAL261, "small"),
    ("小字页 + PAL205", PAGES_SMALL, PAL205, "small"),
    ("大字页 + PAL205", PAGES_MAIN, PAL205, "main"),
    ("大字页 + PAL261", PAGES_MAIN, PAL261, "main"),
]
for name, pages, pal, kind in combos:
    vals3 = Counter()
    bfs = []
    for code in range(0, 256):
        hi, lo = code >> 8, code & 0xFF
        o = pages[hi] + lo * 64 - BASE
        if o < 0 or o + 64 > N:
            continue
        if kind == "small":
            o1 = o + 0x100
            if o1 + 16 > N:
                continue
            m = np.vstack([mat8(decode16(zh[o:o + 16], pal)),
                           mat8(decode16(zh[o1:o1 + 16], pal))])
        else:
            segs = [mat8(decode16(zh[o + k * 16:o + k * 16 + 16], pal))
                    for k in range(4)]
            m = np.vstack([np.hstack([segs[0], segs[1]]),
                           np.hstack([segs[2], segs[3]])])
        c = Counter(int(v) for v in m.flatten())
        for v, n in c.items():
            vals3[v] += n
        bg = c.most_common(1)[0][0]
        bfs.append(c[bg] / m.size)
    print(f"  {name}: 值种类={len(vals3)}  背景占比={np.mean(bfs):.1%}")
    print(f"     值分布: {dict(sorted(vals3.items())[:8])}")

print("\n" + "=" * 78)
print("④ 两张 PAL 的差异（前 16 项）")
print("=" * 78)
print(f"  {'idx':<5} {'PAL205':<10} {'PAL261':<10} 说明")
for k in range(16):
    a = f"{PAL205[k*2]:02x} {PAL205[k*2+1]:02x}"
    b = f"{PAL261[k*2]:02x} {PAL261[k*2+1]:02x}"
    print(f"  [{k:>2}] {a:<10} {b:<10}")
