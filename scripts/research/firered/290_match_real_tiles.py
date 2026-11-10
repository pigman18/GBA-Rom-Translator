"""调研(290) 用 VRAM 里 207 个真实小字 tile，在 ROM 里全量反查。

═══ 290 的突破 ═══
从队伍界面 VRAM 里找到 **207 个真实小字 tile**（7-8 高、5-8 宽），
序号 3/6/9/10/12/13/... 全在页面开头。

这才是要提交的「小字」真相。

本脚本：
 ① 提取这 207 个 tile 的 32B
 ② 用小字页表 + 正确公式解码全部码位，逐字节比对这些 tile
 ③ 找到第一个精确命中，确认公式
 ④ 若命中，导出全量
"""
from __future__ import annotations

import struct
import zlib
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
P = ROOT / "work" / "_probe" / "party261"
vr = (P / "s01_party01_vram.bin").read_bytes()
iw = (P / "s01_party01_iwram.bin").read_bytes()
BASE = 0x08000000
N = len(zh)

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = iw[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

SMALL_PAGES = [0x08B01000, 0x08B40000, 0x08B50000, 0x08B60000, 0x08B70000,
               0x08B80000, 0x08B90000, 0x08BA0000, 0x08BB0000,
               0x08B64000, 0x08B68000]
MAIN_PAGES = [0x089C4230, 0x089555A0, 0x08B55564, 0x08A2725C, 0x08B333A0,
              0x08907C0C, 0x08AD690C, 0x08935A08, 0x08A72610, 0x08AB5404,
              0x089B2B0C]


def mat8(b):
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = b[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


def decode16(src):
    out = bytearray()
    for r3 in range(16):
        p = (r3 // 2) * 2
        v = src[p] if (r3 & 1) else (src[p + 1] if p + 1 < len(src) else 0)
        i = IDX[v]
        off = i * 2
        out += PAL[off:off + 2] if off + 1 < len(PAL) else b'\x00\x00'
    return bytes(out)


# ── ① 提取 VRAM 真实小字 tile ────────────────────────────
targets = {}
for t in range(len(vr) // 32):
    o = t * 32
    b = vr[o:o + 32]
    m = mat8(b)
    vals = set(int(v) for v in m.flatten())
    if len(vals) > 4:
        continue
    bg = max(vals, key=lambda v: int((m == v).sum()))
    nz = (m != bg)
    ink = int(nz.sum())
    if ink < 8 or ink > 50:
        continue
    ys = np.flatnonzero(nz.any(axis=1))
    xs = np.flatnonzero(nz.any(axis=0))
    if not (5 <= len(ys) <= 8 and 3 <= len(xs) <= 8):
        continue
    targets[t] = b

print(f"VRAM 真实小字 tile: {len(targets)} 个")
print(f"  前 20 个序号: {sorted(targets)[:20]}")

# ── ② 全码位 × 多种公式，逐段比对 ───────────────────────
print("\n" + "=" * 78)
print("穷举公式，找能精确命中的")
print("=" * 78)

FORMULAS = {
    "SMALL lo64 seg0": (SMALL_PAGES, lambda hi, lo, c: lo * 64, 0x00),
    "SMALL lo64 seg1": (SMALL_PAGES, lambda hi, lo, c: lo * 64, 0x10),
    "SMALL lo64 seg2": (SMALL_PAGES, lambda hi, lo, c: lo * 64, 0x20),
    "SMALL lo64 seg3": (SMALL_PAGES, lambda hi, lo, c: lo * 64, 0x30),
    "SMALL 512 seg0": (SMALL_PAGES,
                       lambda hi, lo, c: (lo >> 3) * 512 + (c & 7) * 32, 0x00),
    "SMALL 512 seg1": (SMALL_PAGES,
                       lambda hi, lo, c: (lo >> 3) * 512 + (c & 7) * 32, 0x10),
    "SMALL 512 seg2": (SMALL_PAGES,
                       lambda hi, lo, c: (lo >> 3) * 512 + (c & 7) * 32, 0x20),
    "SMALL 512 seg3": (SMALL_PAGES,
                       lambda hi, lo, c: (lo >> 3) * 512 + (c & 7) * 32, 0x30),
    "MAIN lo64 seg0": (MAIN_PAGES, lambda hi, lo, c: lo * 64, 0x00),
    "MAIN lo64 seg1": (MAIN_PAGES, lambda hi, lo, c: lo * 64, 0x10),
    "MAIN 512 seg0": (MAIN_PAGES,
                      lambda hi, lo, c: (lo >> 3) * 512 + (c & 7) * 32, 0x00),
    "MAIN 512 seg1": (MAIN_PAGES,
                      lambda hi, lo, c: (lo >> 3) * 512 + (c & 7) * 32, 0x10),
}

results = []
for name, (pages, offn, seg) in FORMULAS.items():
    hits = 0
    detail = []
    for code in range(0x0B00):
        hi, lo = code >> 8, code & 0xFF
        if hi >= len(pages):
            continue
        a = pages[hi] + offn(hi, lo, code) + seg
        o = a - BASE
        if o < 0 or o + 16 > N:
            continue
        d = decode16(zh[o:o + 16])
        for t, tgt in targets.items():
            if d == tgt:
                hits += 1
                if len(detail) < 6:
                    detail.append((t, code))
    results.append((hits, name, detail))

results.sort(reverse=True)
for hits, name, det in results[:8]:
    print(f"  {name:<18} 命中 {hits:>4}  {[(t, hex(c)) for t, c in det]}")

best = results[0] if results else (0, "", [])
if best[0] == 0:
    print("\n  ✘ 全部 0 命中 —— 小字不是从这些页表解码出来的")
    # 检查：这些小字 tile 是否直接存在于 ROM
    print("\n  直接搜 ROM：")
    found = 0
    for t, b in list(targets.items())[:20]:
        p = zh.find(b)
        if p >= 0:
            found += 1
            print(f"    tile {t} -> 0x{BASE + p:08X}")
    print(f"    命中 {found}/20")
else:
    print(f"\n  ★ 最佳：{best[1]}，命中 {best[0]}")
