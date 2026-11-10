"""小字最终导出 —— 数据用 269 已验证正确的 B 布局，分小图放大渲染。

═══ 本轮所有误判的总结 ═══
数据一直是对的。271-275 我反复换布局、换步长、换判据，
根因是**把 249~2500 个字塞进一张 PNG**，每字只有几像素，肉眼看不清，
就误以为字形错了。

证据：同一套数据（+0x00 + +0x100，步长 64）
  · 8 个字放大 5 倍  -> 清晰可读「中 文 宝 可 梦 盘 三 上 / 下 丛 以 合…」
  · 249 个字         -> 糊成一片

═══ 正确参数（269 已验证）═══
    页表 0x08B74000
    addr = PAGES[hi] + lo * 64
    上半 = decode16(rom[addr + 0x00 : +0x10])
    下半 = decode16(rom[addr + 0x100 : +0x110])
    纵向拼 -> 8 宽 x 16 高

本脚本按此导出，每图 32 字、放大 6 倍。
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
OUT = ROOT / "work" / "_probe" / "smallfont_v" / "final"
OUT.mkdir(parents=True, exist_ok=True)

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = IW261[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

PAGES_SMALL = [0x08B01000, 0x08B40000, 0x08B50000, 0x08B60000, 0x08B70000,
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


def small_glyph(code: int):
    """269 验证过的 B 布局。"""
    hi, lo = code >> 8, code & 0xFF
    if hi >= len(PAGES_SMALL):
        return None
    o = PAGES_SMALL[hi] + lo * 64 - BASE
    if o < 0 or o + 64 > N:
        return None
    o1 = o + 0x100
    if o1 + 16 > N:
        return None
    return np.vstack([mat8(decode16(zh[o:o + 16])),
                      mat8(decode16(zh[o1:o1 + 16]))])


print("=== 导出（布局 B，8x16）===")
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

# 收紧到实际墨迹 bbox（确认是 8x12）
ys, xs = [], []
for _, m, bg, _ in items[:300]:
    nz = np.argwhere(m != bg)
    if len(nz):
        ys.append((nz[:, 0].min(), nz[:, 0].max()))
        xs.append((nz[:, 1].min(), nz[:, 1].max()))
print(f"  y 范围: {min(a for a, b in ys)}..{max(b for a, b in ys)}")
print(f"  x 范围: {min(a for a, b in xs)}..{max(b for a, b in xs)}")

SCALE = 6
GAP = 5
COLS = 8          # 每行 8 字（小图，看得清）
PER = 32          # 每张 32 字


def render(sel, path: Path, name: str):
    rows = (len(sel) + COLS - 1) // COLS
    CW = 8 * SCALE + GAP
    CH = 16 * SCALE + GAP
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


# 第 0 页前 32 字（用来核对「中 文 宝 可 梦…」）
render(items[:32], OUT / "V00_first32.png", "V00_first32.png")

# 全部按每 32 字一张
for bi in range(0, len(items), PER):
    render(items[bi:bi + PER], OUT / f"S{bi//PER:03d}.png",
           f"S{bi//PER:03d}.png")

arr = np.zeros((len(items), 16, 8), dtype=np.uint8)
for i, (_, m, _, _) in enumerate(items):
    arr[i] = m
np.save(OUT / "glyphs.npy", arr)
np.save(OUT / "codes.npy", np.array([c for c, _, _, _ in items], dtype=np.int32))
np.save(OUT / "bgs.npy", np.array([b for _, _, b, _ in items], dtype=np.uint8))
print(f"\n已存 glyphs.npy {arr.shape}  codes.npy")

print("\n=== 前 16 个字的字符画 ===")
for i in range(min(16, len(items))):
    code, m, bg, ink = items[i]
    print(f"\n  码 0x{code:03X}:")
    for y in range(16):
        print("    " + "".join("." if v == bg else
                               ("#" if v > bg else "+") for v in m[y]))
