"""用 IWRAM 0x03003DE0 的小字解码缓冲，反查它来自哪个码位的哪一段。

═══ 242 的决定性发现 ═══
IWRAM 0x03003DE0 里是 `11 11 11 11 11 21 13 21 22 22 22 22 33 23 ...`
—— 与小字 tile 同一套值域（11/21/22/33 等）。

而 207 已证：主字库解码也写到 0x03003DE0。
⇒ **同一缓冲，同一解码函数**。

所以小字**就是**主字库某个码位的解码结果。
237 解出全 0 是因为我用 runtime205 的 PAL 去解 party232 的快照。

本脚本：用 party232 自己的 PAL，遍历全部码位 × 4 段，
精确比对 IWRAM 0x03003DE0 的内容和 VRAM 小字 tile。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
P = ROOT / "work" / "_probe" / "party232"
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
iw = (P / "s05_party_iwram.bin").read_bytes()
vr = (P / "s05_party_vram.bin").read_bytes()
BASE = 0x08000000

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


print("=== IWRAM 0x03003DE0 前 128B（小字解码缓冲）===")
o = 0x03003DE0 - 0x03000000
buf = iw[o:o + 128]
for i in range(0, 128, 32):
    print(f"  +{i:03X}  {buf[i:i+32].hex(' ')}")

print("\n=== 这些缓冲 vs VRAM 小字 tile ===")
for t in (137, 213, 267, 321, 375):
    tgt = vr[t * 32:t * 32 + 32]
    p = buf.find(tgt)
    p2 = iw.find(tgt)
    print(f"  tile {t}: 在缓冲内={p if p>=0 else '-'}  IWRAM 内={('0x%08X'% (0x03000000+p2)) if p2>=0 else '-'}")

# 关键：用 party232 的 PAL 解全部码位，找能产出 IWRAM 缓冲内容的
print("\n=== 全码位 × 4 段 解码，与 IWRAM 0x03003DE0 的 32B 比对 ===")
targets = {}
for k in range(4):
    targets[f"buf{k}"] = buf[k * 32:(k + 1) * 32]

found = []
for hi, pg in enumerate(PAGES4):
    for lo in range(256):
        oo = pg + lo * 64 - BASE
        if oo < 0 or oo + 64 > len(zh):
            continue
        b = zh[oo:oo + 64]
        for k in range(4):
            d = decode16(b[k * 16:(k + 1) * 16], PAL232)
            for name, tgt in targets.items():
                if d == tgt:
                    found.append((name, hi * 256 + lo, k))
print(f"  命中 {len(found)}: {[(n, hex(c), k) for n, c, k in found[:10]]}")

# 若没有，试「整字 64B 拼接」比对 128B 缓冲
print("\n=== 整字（4 段拼 128B）与 IWRAM 缓冲 128B 比对 ===")
best = []
for hi, pg in enumerate(PAGES4):
    for lo in range(256):
        oo = pg + lo * 64 - BASE
        if oo < 0 or oo + 64 > len(zh):
            continue
        b = zh[oo:oo + 64]
        full = b"".join(decode16(b[k * 16:(k + 1) * 16], PAL232) for k in range(4))
        same = sum(1 for x, y in zip(full, buf) if x == y)
        if same > 100:
            best.append((same, hi * 256 + lo))
best.sort(reverse=True)
print(f"  128B 中相同 >100 的: {len(best)}")
for s, c in best[:6]:
    print(f"    码 0x{c:03X}: {s}/128")

# 直接看：buffer 里的 4 段能否拼出一个字
print("\n=== IWRAM 缓冲 128B 按 2x2 拼接（8x8 x4 -> 16x16）===")


def nibs(b):
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = b[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


ms = [nibs(buf[k * 32:(k + 1) * 32]) for k in range(4)]
comb = np.vstack([np.hstack([ms[0], ms[1]]), np.hstack([ms[2], ms[3]])])
bg = 0x11
for y in range(16):
    print("  " + "".join("." if v == bg else ("#" if v >= 0x22 else "+")
                         for v in comb[y]))
