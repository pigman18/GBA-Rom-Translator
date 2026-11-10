"""小字最终结论：步长 32 字节/字，取 +0x00 与 +0x10 两段拼 8x16。

═══ 本轮推导链 ═══
1. 页表 0x08B74000，11 页，原版 100% FF
2. decode16 与大字完全相同（IDX/PAL 共用）
3. 码 0x000 的四段拼出来是：
      +0x00  = 「中」的上半（干净）
      +0x10  = 「中」的下半
      +0x20  = 另一个字的上半（挤压变形）
      +0x30  = 另一个字的下半
   ⇒ **每 64 字节里装了 2 个字，各 32 字节（2 段 x 16B）**
   ⇒ 正确步长是 **32**，不是 64

4. 这与配置表的「宽 8，高 0x0C」吻合：
      8 宽 x 16 高（有效 12 行）

本脚本按步长 32 导出。
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
OUT = ROOT / "work" / "_probe" / "smallfont_step32"
OUT.mkdir(parents=True, exist_ok=True)

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = IW261[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

PAGES_SMALL = [0x08B01000, 0x08B40000, 0x08B50000, 0x08B60000, 0x08B70000,
               0x08B80000, 0x08B90000, 0x08BA0000, 0x08BB0000,
               0x08B64000, 0x08B68000]
STRIDE = 32
MAXCODE = 0x0AFF


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


def small_glyph(code: int):
    """步长 32：+0x00 上半、+0x10 下半，纵向 8x16。"""
    hi, lo = code >> 8, code & 0xFF
    if hi >= len(PAGES_SMALL):
        return None
    o = PAGES_SMALL[hi] + lo * STRIDE - BASE
    if o < 0 or o + 32 > N:
        return None
    return np.vstack([mat8(decode16(zh[o:o + 16])),
                      mat8(decode16(zh[o + 16:o + 32]))])


print("=== 导出小字（步长 32，8x16）===")
items = []
for code in range(MAXCODE + 1):
    m = small_glyph(code)
    if m is None:
        continue
    c = Counter(int(v) for v in m.flatten())
    bg = c.most_common(1)[0][0]
    ink = int((m != bg).sum())
    if ink < 6:
        continue
    items.append((code, m, bg, ink))
print(f"  有内容码位 {len(items)}")

ys, xs = [], []
for _, m, bg, _ in items[:300]:
    nz = np.argwhere(m != bg)
    if len(nz):
        ys.append(nz[:, 0].max() - nz[:, 0].min() + 1)
        xs.append(nz[:, 1].max() - nz[:, 1].min() + 1)
print(f"  墨迹高度 均值 {np.mean(ys):.1f} 最大 {max(ys) if ys else 0}")
print(f"  墨迹宽度 均值 {np.mean(xs):.1f} 最大 {max(xs) if xs else 0}")
print(f"  背景占比 均值 {np.mean([ink for _, _, _, ink in items]) / 128:.1%}")

SCALE = 6
GAP = 4
COLS = 16
CW = 8 * SCALE + GAP
CH = 16 * SCALE + GAP


def render(sel, path: Path, name: str):
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
for pi in range(11):
    sel = [x for x in items if (x[0] >> 8) == pi]
    for k in range(0, len(sel), 64):
        render(sel[k:k + 64], OUT / f"P{pi:02d}_{k//64:02d}.png",
               f"P{pi:02d}_{k//64:02d}.png")

arr = np.zeros((len(items), 16, 8), dtype=np.uint8)
for i, (_, m, _, _) in enumerate(items):
    arr[i] = m
np.save(OUT / "glyphs.npy", arr)
np.save(OUT / "codes.npy", np.array([c for c, _, _, _ in items], dtype=np.int32))
print(f"\n已存 glyphs.npy {arr.shape}")

print("\n=== 前 8 个字 ===")
for i in range(min(8, len(items))):
    code, m, bg, ink = items[i]
    print(f"\n  码 0x{code:03X}:")
    for y in range(16):
        print("    " + "".join("." if v == bg else "#" for v in m[y]))
