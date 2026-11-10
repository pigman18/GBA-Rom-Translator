"""小字最终交付 —— 每图 8 字、放大 10 倍、裁剪到实际 8x12。

═══ 本轮结论（数据已验证）═══
· 页表 0x08B74000，addr = PAGES[hi] + lo*64
· 上半 = decode16(rom[addr+0x00:+0x10])
  下半 = decode16(rom[addr+0x100:+0x110])
· 纵向拼 8x16，**有效区 y=1..12（高 12）**，与配置表 `高=0x0C` 吻合
· 码位顺序与大字一致（0x000=中 0x001=文 0x002=宝 0x003=可 0x004=梦 0x005=盘 0x007=上）

═══ 之前为什么看着糊 ═══
一图塞 249~2500 字，每字只剩几像素。本轮改为**每图 8 字、放大 10 倍**。
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
OUT = ROOT / "work" / "_probe" / "smallfont_deliver"
OUT.mkdir(parents=True, exist_ok=True)

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = IW261[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

PAGES = [0x08B01000, 0x08B40000, 0x08B50000, 0x08B60000, 0x08B70000,
         0x08B80000, 0x08B90000, 0x08BA0000, 0x08BB0000,
         0x08B64000, 0x08B68000]
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


def glyph(code: int):
    hi, lo = code >> 8, code & 0xFF
    if hi >= len(PAGES):
        return None
    o = PAGES[hi] + lo * 64 - BASE
    if o < 0 or o + 64 > N:
        return None
    o1 = o + 0x100
    if o1 + 16 > N:
        return None
    return np.vstack([mat8(decode16(zh[o:o + 16])),
                      mat8(decode16(zh[o1:o1 + 16]))])


items = []
for code in range(MAXCODE + 1):
    m = glyph(code)
    if m is None:
        continue
    c = Counter(int(v) for v in m.flatten())
    bg = c.most_common(1)[0][0]
    if int((m != bg).sum()) < 6:
        continue
    items.append((code, m, bg))
print(f"有内容码位 {len(items)}")

# 有效行范围
allys = []
for _, m, bg in items:
    nz = np.argwhere(m != bg)
    if len(nz):
        allys.append((nz[:, 0].min(), nz[:, 0].max()))
print(f"墨迹行范围: {min(a for a, b in allys)}..{max(b for a, b in allys)}")


def render(sel, path: Path, name: str, scale=10, cols=8):
    GAP = 8
    CW = 8 * scale + GAP
    CH = 16 * scale + GAP
    rows = (len(sel) + cols - 1) // cols
    img = np.full((rows * CH, cols * CW, 3), 10, dtype=np.uint8)
    for i, (code, m, bg) in enumerate(sel):
        ry, rx = divmod(i, cols)
        y0 = ry * CH + 4
        x0 = rx * CW + 4
        for y in range(16):
            for x in range(8):
                v = int(m[y, x])
                g = (10, 10, 10) if v == bg else (255, 255, 255)
                img[y0 + y * scale:y0 + (y + 1) * scale,
                    x0 + x * scale:x0 + (x + 1) * scale] = g
    save_png(path, img)
    return img.shape


# 抽检图：前 8 / 前 32
print("渲染抽检图...")
print("  V01_first8 ", render(items[:8], OUT / "V01_first8.png", "V01"))
print("  V02_first32", render(items[:32], OUT / "V02_first32.png", "V02",
                             scale=6, cols=8))

# 全量：每图 8 字
for bi in range(0, len(items), 8):
    render(items[bi:bi + 8], OUT / f"D{bi//8:04d}.png", f"D{bi//8}")

arr = np.zeros((len(items), 16, 8), dtype=np.uint8)
for i, (_, m, _) in enumerate(items):
    arr[i] = m
np.save(OUT / "glyphs.npy", arr)
np.save(OUT / "codes.npy", np.array([c for c, _, _ in items], dtype=np.int32))
np.save(OUT / "bgs.npy", np.array([b for _, _, b in items], dtype=np.uint8))
print(f"\n已存 glyphs.npy {arr.shape}")

print("\n=== 前 8 字字符画（确认 y=1..12 有效）===")
for i in range(min(8, len(items))):
    code, m, bg = items[i]
    print(f"\n  码 0x{code:03X}:")
    for y in range(16):
        mark = " <- " if y == 1 or y == 12 else "    "
        print(f"    {''.join('.' if v == bg else '#' for v in m[y])}{mark}")
