"""用小字专用页表 0x08B74000 直接导出小字字库。

═══ 253/254 已确证 ═══
小字配置表 @0x08E25F4C：
    [-5] 0x080060ED   取字形函数
    [-4] 0x08B74000   ★小字页表（11 项）
    [-3] 0x08B6C000   默认页
    [-2] 0x00000100   ★段偏移1 = +0x100
    [-1] 0x00000110   ★段偏移2 = +0x110
    [+0] 0x08002F5D   解码函数（与主字库同一个）
    [+2] 0x020228FC   输出缓冲

小字页表 0x08B74000（11 项，每页原版 100% FF）：
    0x08B01000 0x08B40000 0x08B50000 0x08B60000 0x08B70000
    0x08B80000 0x08B90000 0x08BA0000 0x08BB0000 0x08B64000 0x08B68000

段布局（从 244 号反汇编的小字分支得到）：
    段0: 源 +0x00  -> 目标 +0x00
    段1: 源 +0x100 -> 目标 +0x40
    宽=8，高=0x0C 或 0x10

本脚本按此导出，并**用 VRAM 里已知的小字 tile 验证**。
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
iw = (ROOT / "work/_probe/party232/s05_party_iwram.bin").read_bytes()
vr = (ROOT / "work/_probe/party232/s05_party_vram.bin").read_bytes()
BASE = 0x08000000
N = len(zh)

OUT = ROOT / "work" / "_probe" / "smallf_export"
OUT.mkdir(parents=True, exist_ok=True)

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = iw[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

PAGES_SMALL = [0x08B01000, 0x08B40000, 0x08B50000, 0x08B60000, 0x08B70000,
               0x08B80000, 0x08B90000, 0x08BA0000, 0x08BB0000,
               0x08B64000, 0x08B68000]

SEG_OFF = 0x100
DEFAULT_PAGE = 0x08B6C000


def decode16(src, pal):
    out = bytearray()
    for r3 in range(16):
        p = (r3 // 2) * 2
        v = src[p] if (r3 & 1) else (src[p + 1] if p + 1 < len(src) else 0)
        i = IDX[v]
        off = i * 2
        out += pal[off:off + 2] if off + 1 < len(pal) else b'\x00\x00'
    return bytes(out)


def nibs(b):
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = b[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


def small_segs(code, pal):
    """返回 (段0的32B, 段1的32B)。"""
    hi, lo = code >> 8, code & 0xFF
    page = PAGES_SMALL[hi] if hi < len(PAGES_SMALL) else DEFAULT_PAGE
    base = page + lo * 64
    o0 = base - BASE
    o1 = base + SEG_OFF - BASE
    d0 = decode16(zh[o0:o0 + 16], pal) if 0 <= o0 and o0 + 16 <= N else b"\x00" * 32
    d1 = decode16(zh[o1:o1 + 16], pal) if 0 <= o1 and o1 + 16 <= N else b"\x00" * 32
    return d0, d1


# ── 验证：能否对上 VRAM 里的小字 tile ─────────────────────
print("=== 验证：小字页表能否解出 VRAM 里的小字 ===")
targets = {}
for t in (137, 213, 267, 321, 375):
    targets[t] = vr[t * 32:t * 32 + 32]

hits = []
for hi, page in enumerate(PAGES_SMALL):
    for lo in range(256):
        code = hi * 256 + lo
        d0, d1 = small_segs(code, PAL)
        for t, tgt in targets.items():
            if d0 == tgt:
                hits.append((t, code, 0))
            if d1 == tgt:
                hits.append((t, code, 1))
print(f"  命中 {len(hits)}: {[(t, hex(c), s) for t, c, s in hits[:12]]}")

if not hits:
    print("  0 命中 —— 试其他 PAL")
    # 用 runtime205 的 PAL
    iw205 = (ROOT / "work/_probe/runtime205/t000_prove_iwram.bin").read_bytes()
    PAL205 = iw205[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]
    hits2 = []
    for hi, page in enumerate(PAGES_SMALL):
        for lo in range(256):
            code = hi * 256 + lo
            d0, d1 = small_segs(code, PAL205)
            for t, tgt in targets.items():
                if d0 == tgt:
                    hits2.append((t, code, 0))
                if d1 == tgt:
                    hits2.append((t, code, 1))
    print(f"  runtime205 PAL 命中 {len(hits2)}: {[(t, hex(c), s) for t, c, s in hits2[:12]]}")

    if not hits2:
        print("\n  仍然 0 命中。直接看页里有什么：")
        o = PAGES_SMALL[0] - BASE
        for i in range(0, 0x80, 16):
            seg = zh[o + i:o + i + 16]
            jseg = ja[o + i:o + i + 16]
            mk = " *汉化改" if seg != jseg else ""
            print(f"    0x{PAGES_SMALL[0] + i:08X}  {seg.hex(' ')}{mk}")
        # 段0 与段1 的实际内容
        print("\n  码 0x000 的段0/段1 源:")
        for seg_off in (0, SEG_OFF):
            s = zh[o + seg_off:o + seg_off + 16]
            print(f"    +0x{seg_off:03X}: {s.hex(' ')}")
            d = decode16(s, PAL)
            m = nibs(d)
            print(f"      解码: {d[:16].hex(' ')}")
            for y in range(8):
                print("      " + "".join("." if v == 0x11 else
                                         ("#" if v >= 0x22 else "+") for v in m[y]))

# ── 无论命中与否，先统计所有码位的墨量 ─────────────────────
print("\n=== 全部码位（11 页 × 256）的段0/段1 墨量统计 ===")
tot0 = tot1 = 0
for hi in range(11):
    n0 = n1 = 0
    for lo in range(256):
        code = hi * 256 + lo
        d0, d1 = small_segs(code, PAL)
        m0 = nibs(d0)
        m1 = nibs(d1)
        if int((m0 != 0x11).sum()) > 3:
            n0 += 1
        if int((m1 != 0x11).sum()) > 3:
            n1 += 1
    tot0 += n0
    tot1 += n1
    print(f"  页{hi} 0x{PAGES_SMALL[hi]:08X}: 段0 有墨 {n0:>3}/256  段1 有墨 {n1:>3}/256")
print(f"  合计: 段0 {tot0}  段1 {tot1}")
