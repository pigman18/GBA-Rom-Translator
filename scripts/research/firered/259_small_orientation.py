"""修正：小字是 8 宽 × 16 高（不是 8×8）。

═══ 258/259 的发现 ═══
decode16 输出 32 字节。按 4bpp 算：
    32 字节 = 2 字节/行 × 16 行  ⇒ 8 宽 × 16 高
    32 字节 = 4 字节/行 × 8 行   ⇒ 8 宽 × 8 高

之前按 8×8（每行 4 字节）解读，得到「每行前 4 像素都是 1111」——
那是把两行挤成了一行。按 16 高（每行 2 字节）才对。

验证：块0 的解码 = 
    1111111111112113 1111211321222222 2133233321132113 2113211321222222
  拆成 16 组 2 字节（= 每行 4 像素）？
  不对，8 宽 4bpp = 4 字节/行。32B / 4B = 8 行。

所以 decode16 的 32 字节就是 8x8（每行 4 字节）。
那「前 4 像素 1111」是因为……字形本身左边就是空的？

看块0 的 8x8：
    11111111
    11111231
    11111231
    12222222
    12333233
    12311231
    12311231
    12222222
这是「中」字！左边竖线应该在 x=1~2，但显示在 x=5。
⇒ 字形水平错位 4 像素。

原因：decode16 的读序（每对字节交换）导致像素重排。
本脚本试「不交换」的读序，看是否能得到正确的「中」。
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
iw = (ROOT / "work/_probe/party232/s05_party_iwram.bin").read_bytes()
BASE = 0x08000000
OUT = ROOT / "work" / "_probe" / "smallfont2"
OUT.mkdir(parents=True, exist_ok=True)

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = iw[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]
PAGE0 = 0x08B01000


def save_png(path, arr):
    h, w, _ = arr.shape
    raw = b''.join(b'\x00' + arr[y].tobytes() for y in range(h))

    def chunk(tag, data):
        c = tag + data
        return (struct.pack('>I', len(data)) + c
                + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF))

    path.write_bytes(b'\x89PNG\r\n\x1a\n'
                     + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(raw, 9))
                     + chunk(b'IEND', b''))


def mat(blob: bytes, w: int = 8, h: int = 8):
    m = np.zeros((h, w), dtype=np.uint8)
    per = w // 2
    for y in range(h):
        for x in range(w):
            off = y * per + x // 2
            if off >= len(blob):
                break
            v = blob[off]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


def dec(src, swap=True):
    """swap=True 是原 decode16 的读序；False 是顺序读。"""
    out = bytearray()
    for r3 in range(16):
        p = (r3 // 2) * 2
        if swap:
            v = src[p] if (r3 & 1) else (src[p + 1] if p + 1 < len(src) else 0)
        else:
            v = src[r3] if r3 < len(src) else 0
        i = IDX[v]
        off = i * 2
        out += PAL[off:off + 2] if off + 1 < len(PAL) else b'\x00\x00'
    return bytes(out)


o = PAGE0 - BASE
print("=== 各种读序 + 尺寸组合，看哪个能得到「中」 ===")
combos = [
    ("swap + 8x8", True, 8, 8),
    ("noshift + 8x8", False, 8, 8),
    ("swap + 8x16", True, 8, 16),
    ("noshift + 8x16", False, 8, 16),
    ("swap + 16x8", True, 16, 8),
    ("noshift + 16x8", False, 16, 8),
]

for name, sw, w, h in combos:
    print(f"\n--- {name} ---")
    for k in range(3):
        src = zh[o + k * 16:o + k * 16 + 16]
        d = dec(src, sw)
        m = mat(d, w, h)
        print(f"  块{k}:")
        for y in range(h):
            print("    " + "".join("#" if v == 3 else ("+" if v == 2 else ".")
                                   for v in m[y]))

# 也试「32B 直接当 8x16」
print("\n--- 32B 直接当 8x16 (4bpp) ---")
for k in range(3):
    src = zh[o + k * 32:o + k * 32 + 32]
    m = mat(src, 8, 16)
    print(f"  块{k}:")
    for y in range(16):
        print("    " + "".join("#" if v >= 2 else "." for v in m[y]))
