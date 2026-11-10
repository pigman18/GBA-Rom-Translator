"""用匹配的 PAL 表重做验证。

═══ 237 的根因 ═══
我拿 party232（队伍界面）的 IWRAM，却用 runtime205（菜单）的 PAL 逻辑去解码，
所以主字库全解成空。

实证：
  runtime205 PAL = aa aa / aa 1a / aa ca ...   （菜单，底色 a）
  party232   PAL = 11 11 / 11 21 / 11 31 ...   （队伍，底色 1）

⇒ PAL 是**按界面重建**的运行时表，不能跨界面混用。

本脚本：
 ① 用 party232 自己的 PAL 解主字库，看是否能解出小字/大字
 ② 用 runtime205 的 PAL 解 party 快照里的小字，反向也不行 → 确认隔离
 ③ 给出结论：字库 PAGES4 是同一套，PAL 换界面就变
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
BASE = 0x08000000

IW205 = (ROOT / "work/_probe/runtime205/t000_prove_iwram.bin").read_bytes()
IW232 = (ROOT / "work/_probe/party232/s05_party_iwram.bin").read_bytes()
VR232 = (ROOT / "work/_probe/party232/s05_party_vram.bin").read_bytes()

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAGES4 = [0x089C4230, 0x089555A0, 0x08B55564, 0x08A2725C, 0x08B333A0,
          0x08907C0C, 0x08AD690C, 0x08935A08, 0x08A72610, 0x08AB5404,
          0x089B2B0C]


def get_pal(iw):
    return iw[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]


PAL205 = get_pal(IW205)
PAL232 = get_pal(IW232)


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


def ink_of(d, bg):
    m = nibs(d)
    return int(((m != bg) & (m != 0)).sum())


print("=== 用 party232 自己的 PAL 解主字库 ===")
for k in range(4):
    nz = 0
    for pg in PAGES4[:1]:
        for lo in range(0, 64):
            o = pg + lo * 64 - BASE
            if o < 0 or o + 64 > len(zh):
                continue
            d = decode16(zh[o + k * 16:o + k * 16 + 16], PAL232)
            m = nibs(d)
            if int((m != 0x11).sum()) > 3:
                nz += 1
    print(f"  段{k}: 前 64 码位中有墨 {nz}")

print("\n=== 码 0x000 用两种 PAL 解出的第 0 段 ===")
o = PAGES4[0] - BASE
src = zh[o:o + 16]
for name, pal, bg in (("runtime205", PAL205, 0xAA), ("party232", PAL232, 0x11)):
    d = decode16(src, pal)
    m = nibs(d)
    print(f"\n  {name} (bg=0x{bg:02X}): {d[:16].hex(' ')}")
    for y in range(8):
        print("    " + "".join("." if v == bg else
                               ("#" if v == 12 else ("+" if v == 11 else "?"))
                               for v in m[y]))

print("\n=== 小字 tile（VRAM 137）用 party232 PAL 能否反查主字库 ===")
tgt = VR232[137 * 32:137 * 32 + 32]
found = []
for hi, pg in enumerate(PAGES4):
    for lo in range(256):
        o = pg + lo * 64 - BASE
        if o < 0 or o + 64 > len(zh):
            continue
        b = zh[o:o + 64]
        for k in range(4):
            if decode16(b[k * 16:(k + 1) * 16], PAL232) == tgt:
                found.append((hi * 256 + lo, k))
print(f"  命中 {len(found)}: {[(hex(c), k) for c, k in found[:8]]}")

# 如果还是 0，说明小字确实来自另一处。
# 用 runtime205 PAL 也试一次
print("\n=== 用 runtime205 PAL 试 ===")
found2 = []
for hi, pg in enumerate(PAGES4):
    for lo in range(0, 256):
        o = pg + lo * 64 - BASE
        if o < 0 or o + 64 > len(zh):
            continue
        b = zh[o:o + 64]
        for k in range(4):
            if decode16(b[k * 16:(k + 1) * 16], PAL205) == tgt:
                found2.append((hi * 256 + lo, k))
print(f"  命中 {len(found2)}: {[(hex(c), k) for c, k in found2[:8]]}")
