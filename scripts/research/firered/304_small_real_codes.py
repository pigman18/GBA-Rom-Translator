"""调研(304) 用小字函数 0x080062B4 的真实码位导出。

═══ 303 + GDB 实测（决定性）═══
队伍界面命中三个取字形函数：
    0x080062B4  x68   宽8  高12   页表 0x081CEDF4   ← **小字**
    0x081DB3EE  x51   宽12 高13   页表 0x08B74000   ← 大字
    0x08006354  x23   WIDTH 高12  页表 0x081D6DF4

宽高实测分布：宽=8 高=12 出现 72 次（最多），宽=12 高=13 出现 50 次。

⇒ 小字函数就是 0x080062B4，页表 0x081CEDF4。

═══ 285 为什么解出假名 ═══
285 用的公式 addr = PAGES + (code&0xF)*16 + (code>>4)*512 是凭反汇编推的，
但没有用**真实码位**验证。

302/303 抓到的真实码位：0x00A8、0x00BA、0x00A5、0x01AC、0x010E、0x0084...

本脚本：用这些真实码位，配上多种公式，看哪个能解出「有意义的中文」。
再和 VRAM 里 8x8 tile 比对。
"""
from __future__ import annotations

import struct
import zlib
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated" / "宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
P = ROOT / "work" / "_probe" / "party261"
vr = (P / "s01_party01_vram.bin").read_bytes()
iw = (P / "s01_party01_iwram.bin").read_bytes()
BASE = 0x08000000
N = len(zh)
OUT = ROOT / "work" / "_probe" / "small304"
OUT.mkdir(parents=True, exist_ok=True)

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = iw[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

TBL_SMALL = 0x081CEDF4     # 0x080062B4 用的页表
REAL_CODES = [0x00A8, 0x00BA, 0x00A5, 0x01AC, 0x010E, 0x0084, 0x0085,
              0x00BC, 0x010F, 0x01AD]


def save_png(path, arr, scale=1):
    if scale > 1:
        arr = np.repeat(np.repeat(arr, scale, axis=0), scale, axis=1)
    h, w, _ = arr.shape
    raw = b"".join(b"\x00" + arr[y].tobytes() for y in range(h))

    def chunk(tag, data):
        c = tag + data
        return (struct.pack('>I', len(data)) + c
                + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF))

    path.write_bytes(b'\x89PNG\r\n\x1a\n'
                     + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(raw, 9))
                     + chunk(b'IEND', b''))


def decode16(src):
    out = bytearray()
    for r3 in range(16):
        p = (r3 // 2) * 2
        v = src[p] if (r3 & 1) else (src[p + 1] if p + 1 < len(src) else 0)
        i = IDX[v]
        off = i * 2
        out += PAL[off:off + 2] if off + 1 < len(PAL) else b'\x00\x00'
    return bytes(out)


def mat8(b):
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = b[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


BG = PAL[0] & 0xF

# ── 用真实码位 + 多种公式，看哪个出「有意义的形状」──
print("=" * 78)
print(f"用真实码位 {[hex(c) for c in REAL_CODES[:4]]} 试各种公式")
print("=" * 78)

FORMULAS = {
    "A: (code&0xF)*16 + (code>>4)*512":
        lambda c: (c & 0xF) * 16 + (c >> 4) * 512,
    "B: (code&7)*32 + ((code>>3)&0x1F)*512":
        lambda c: (c & 7) * 32 + ((c >> 3) & 0x1F) * 512,
    "C: code*64": lambda c: c * 64,
    "D: (code&0xFF)*64": lambda c: (c & 0xFF) * 64,
    "E: code*32": lambda c: c * 32,
    "F: (code&0x3F)*32 + (code>>6)*2048":
        lambda c: (c & 0x3F) * 32 + (c >> 6) * 2048,
}

best = None
for fname, fn in FORMULAS.items():
    print(f"\n--- {fname} ---")
    for code in REAL_CODES[:3]:
        a = TBL_SMALL + fn(code)
        o = a - BASE
        if o < 0 or o + 16 > N:
            print(f"  码 0x{code:03X}: 越界")
            continue
        d = decode16(zh[o:o + 16])
        m = mat8(d)
        vals = Counter(int(v) for v in m.flatten())
        bg = vals.most_common(1)[0][0]
        ink = int((m != bg).sum())
        print(f"  码 0x{code:03X} @0x{a:08X}  墨={ink}")
        for y in range(8):
            print("      " + "".join("." if v == bg else "#" for v in m[y]))
        # 评分：墨量 8..40 且不是满格
        if 6 <= ink <= 45:
            score = 1
            if best is None:
                best = (fname, code, m, bg)

# ── 关键：这 32 字节是否在 VRAM 里存在 ──────────────────
print("\n" + "=" * 78)
print("比对：小字函数解出的 32B 是否出现在 VRAM 中")
print("=" * 78)
vr_set = set()
for t in range(len(vr) // 32):
    vr_set.add(vr[t * 32:t * 32 + 32])

found = 0
for fname, fn in FORMULAS.items():
    cnt = 0
    for code in range(0, 0x200):
        a = TBL_SMALL + fn(code)
        o = a - BASE
        if o < 0 or o + 16 > N:
            continue
        if decode16(zh[o:o + 16]) in vr_set:
            cnt += 1
    if cnt:
        print(f"  {fname}: {cnt} 个码位命中 VRAM")
        found += cnt
if not found:
    print("  ✘ 全部 0 命中")
