"""调研(285) 用小字函数 0x080062B4 的真实公式导出。

═══ 284 反汇编确证的公式（小字，宽8 高0xC）═══
080062B6  lsls  r0, r0, #0x10       r0 = code << 16
080062B8  lsrs  r4, r0, #0x14       r4 = (code<<16)>>20 = code >> 4
080062BA  lsls  r4, r4, #9          r4 = (code>>4) * 512
080062C0  ands  r1, r0 (0xF0000)    r1 = (code<<16) & 0xF0000
080062C2  lsrs  r1, r1, #0xc        r1 = (code<<16)>>12 & 0xF0 -> 页号*16?
080062C4  ldr   r0, [pc]            0x081CEDF4   ← 页表
080062C6  adds  r1, r1, r0
080062C8  adds  r4, r4, r1          addr = 页表 + r1 + (code>>4)*512

⚠ 注意 080062C2 的 lsrs #0xc 作用于 r0（= code<<16）的掩码结果，
   (code<<16) & 0xF0000  = (code & 0xF) << 16
   再 >> 12 = (code & 0xF) << 4
   ⇒ r1 = 页表 + (code & 0xF) * 16

所以完整公式：
   addr = 0x081CEDF4 + (code & 0xF)*16 + (code >> 4)*512

═══ 为什么之前解出全空 ═══
我用的是 (code>>16) 作为页号，恒为 0。
正确是 (code & 0xF) * 16。

本脚本按正确公式导出。
"""
from __future__ import annotations

import struct
import zlib
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
IW261 = (ROOT / "work/_probe/party261/s01_party01_iwram.bin").read_bytes()
BASE = 0x08000000
N = len(zh)
OUT = ROOT / "work" / "_probe" / "smallfont_real"
OUT.mkdir(parents=True, exist_ok=True)

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = IW261[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

PAGES = 0x081CEDF4          # 小字页表（0x080062B4 用）
PAGES2 = 0x081EF13C         # 另一套（0x08006640 用）


def save_png(path: Path, arr: np.ndarray) -> None:
    h, w, _ = arr.shape
    raw = b"".join(b"\x00" + arr[y].tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return (struct.pack('>I', len(data)) + c
                + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF))

    path.write_bytes(b'\x89PNG\r\n\x1a\n'
                     + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(raw, 9))
                     + chunk(b'IEND', b''))


def decode16(src: bytes) -> bytes:
    out = bytearray()
    for r3 in range(16):
        p = (r3 // 2) * 2
        v = src[p] if (r3 & 1) else (src[p + 1] if p + 1 < len(src) else 0)
        i = IDX[v]
        off = i * 2
        out += PAL[off:off + 2] if off + 1 < len(PAL) else b'\x00\x00'
    return bytes(out)


def mat8(b: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = b[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


def glyph(code: int):
    """addr = PAGES + (code & 0xF)*16 + (code >> 4)*512，两段 +0x00/+0x100。"""
    a = PAGES + (code & 0xF) * 16 + (code >> 4) * 512
    o = a - BASE
    if o < 0 or o + 0x110 > N:
        return None
    o1 = o + 0x100
    return np.vstack([mat8(decode16(zh[o:o + 16])),
                      mat8(decode16(zh[o1:o1 + 16]))])


BG = PAL[0] & 0xF
print(f"背景 nibble = {BG}")
print("=" * 78)
print("用正确公式解 前 16 个码位")
print("=" * 78)
for code in range(16):
    m = glyph(code)
    if m is None:
        print(f"  码 0x{code:03X}: 越界")
        continue
    ink = int((m != BG).sum())
    print(f"\n  码 0x{code:03X}  墨={ink}:")
    for y in range(16):
        print("    " + "".join("." if v == BG else "#" for v in m[y]))

# 统计全部码位
print("\n" + "=" * 78)
print("全部码位 0x000..0x0AFF 的墨量统计")
print("=" * 78)
items = []
for code in range(0x0B00):
    m = glyph(code)
    if m is None:
        continue
    c = Counter(int(v) for v in m.flatten())
    bg = c.most_common(1)[0][0]
    ink = int((m != bg).sum())
    if ink >= 6:
        items.append((code, m, bg, ink))
print(f"  有内容码位 {len(items)}")
if items:
    print(f"  前 20 个码位: {[hex(c) for c, _, _, _ in items[:20]]}")

    SCALE = 6
    GAP = 4
    COLS = 16
    CW = 8 * SCALE + GAP
    CH = 16 * SCALE + GAP

    def render(sel, path, name):
        rows = (len(sel) + COLS - 1) // COLS
        img = np.full((rows * CH, COLS * CW, 3), 12, dtype=np.uint8)
        for i, (code, m, bg, ink) in enumerate(sel):
            ry, rx = divmod(i, COLS)
            y0 = ry * CH + 2
            x0 = rx * CW + 2
            for y in range(16):
                for x in range(8):
                    v = int(m[y, x])
                    g = (12, 12, 12) if v == bg else (255, 255, 255)
                    img[y0 + y * SCALE:y0 + (y + 1) * SCALE,
                        x0 + x * SCALE:x0 + (x + 1) * SCALE] = g
        save_png(path, img)
        print(f"  ✔ {name}  ({img.shape[1]}x{img.shape[0]}, {len(sel)} 字)")

    render(items[:32], OUT / "VERIFY_32.png", "VERIFY_32.png")
    arr = np.zeros((len(items), 16, 8), dtype=np.uint8)
    for i, (_, m, _, _) in enumerate(items):
        arr[i] = m
    np.save(OUT / "glyphs.npy", arr)
    np.save(OUT / "codes.npy", np.array([c for c, _, _, _ in items], dtype=np.int32))
    print(f"  已存 glyphs.npy {arr.shape}")
