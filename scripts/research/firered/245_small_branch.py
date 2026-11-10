"""用小字分支的算法导出小字字库。

═══ 244 的决定性发现 ═══
0x081DB3EE 函数里有三条分支，之前只分析了「四段 +0x10」那条：

  ── 主字库（大字）@ 0x081DB424 ──
      bl  0x081DB49C   ; 段0: 源+0x00 -> 目标+0x00
      源+0x10 -> 目标+0x20
      源+0x100 -> 目标+0x40
      源+0x110 -> 目标+0x60
      宽 = WIDTH[码]（0x0A/0x0C），高 = 0x0D 常量

  ── ★小字分支1 @ 0x081DB45C ──
      bl  0x081DB49C   ; 段0: 源+0x00 -> 目标+0x00
      源+0x100 -> 目标+0x40
      **宽 = 8，高 = 0x0C**

  ── ★小字分支2 @ 0x081DB47C ──
      bl  0x081DB49C   ; 段0: 源+0x00 -> 目标+0x00
      源+0x100 -> 目标+0x40
      **宽 = 8，高 = 0x10**

⇒ 小字每字 2 段，第 2 段在 +0x100（而大字第 2 段在 +0x10）。
   这解释了为什么我之前按 +0x10 解出来全是乱的。

地址公式同为：addr = PAGES4[hi] + lo*64

本脚本：按小字分支解码，导出全部小字。
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
iw = (ROOT / "work/_probe/party232/s05_party_iwram.bin").read_bytes()
vr = (ROOT / "work/_probe/party232/s05_party_vram.bin").read_bytes()
BASE = 0x08000000
OUT = ROOT / "work" / "_probe" / "smallfont_final"
OUT.mkdir(parents=True, exist_ok=True)

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL232 = iw[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]
PAGES4 = [0x089C4230, 0x089555A0, 0x08B55564, 0x08A2725C, 0x08B333A0,
          0x08907C0C, 0x08AD690C, 0x08935A08, 0x08A72610, 0x08AB5404,
          0x089B2B0C]


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


def small_glyph(code, pal):
    """小字分支：2 段，第 2 段在 +0x100。返回 8 宽 x 16 高的矩阵。"""
    hi, lo = code >> 8, code & 0xFF
    if hi >= len(PAGES4):
        return None
    base = PAGES4[hi] + lo * 64
    # 段0
    o0 = base - BASE
    if o0 < 0 or o0 + 16 > len(zh):
        return None
    d0 = decode16(zh[o0:o0 + 16], pal)
    # 段1：源 +0x100
    o1 = base + 0x100 - BASE
    if o1 < 0 or o1 + 16 > len(zh):
        d1 = b"\x00" * 32
    else:
        d1 = decode16(zh[o1:o1 + 16], pal)
    return np.vstack([nibs(d0), nibs(d1)])


# ── 验证：能否解出 VRAM 里的小字 ──────────────────────────
print("=== 用小字算法解，找 VRAM 里的小字 tile ===")
targets = {}
for t in (137, 213, 267, 321, 375):
    targets[t] = vr[t * 32:t * 32 + 32]

hits = []
for hi, pg in enumerate(PAGES4):
    for lo in range(256):
        code = hi * 256 + lo
        m = small_glyph(code, PAL232)
        if m is None:
            continue
        # 上半 = 第 0 段解码结果
        base = PAGES4[hi] + lo * 64
        o0 = base - BASE
        if o0 < 0 or o0 + 16 > len(zh):
            continue
        d0 = decode16(zh[o0:o0 + 16], PAL232)
        d1off = base + 0x100 - BASE
        d1 = decode16(zh[d1off:d1off + 16], PAL232) if 0 <= d1off and d1off + 16 <= len(zh) else b"\x00" * 32
        for t, tgt in targets.items():
            if d0 == tgt:
                hits.append((t, code, 0))
            if d1 == tgt:
                hits.append((t, code, 1))
print(f"命中 {len(hits)}: {[(t, hex(c), s) for t, c, s in hits[:12]]}")

if not hits:
    print("  仍然 0 命中 —— 小字分支可能还有别的偏移")
    # 试各种偏移
    print("\n=== 穷举偏移：源 +0x00, +0x10, +0x40, +0x60, +0x100, +0x110 ... ===")
    for off in (0x00, 0x10, 0x40, 0x60, 0x80, 0xC0, 0x100, 0x110, 0x140, 0x160,
                0x200, 0x300):
        cnt = 0
        for hi, pg in enumerate(PAGES4):
            for lo in range(0, 256, 8):
                base = PAGES4[hi] + lo * 64 + off
                o = base - BASE
                if o < 0 or o + 16 > len(zh):
                    continue
                d = decode16(zh[o:o + 16], PAL232)
                if d in targets.values():
                    cnt += 1
        if cnt:
            print(f"  偏移 +0x{off:03X}: {cnt} 个命中")

# ── 无论如何，先看看小字分支解出来长什么样 ────────────────
print("\n\n=== 码 0x000..0x00F 用小字算法解出的结果（8x16）===")
for code in range(0x10):
    m = small_glyph(code, PAL232)
    if m is None:
        continue
    print(f"\n  码 0x{code:03X}:")
    for y in range(16):
        print("    " + "".join("." if v == 0x11 else
                               ("#" if v >= 0x22 else "+") for v in m[y]))
