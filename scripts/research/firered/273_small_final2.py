"""小字最终导出 —— 与大字完全相同的 4 段 2x2 布局。

═══ 272 的结论 ═══
6 种布局的背景占比：
    L1_2x2 (同大字)     63.3%  ← 最高
    L2_vstack           62.9%
    L3_hstack           62.9%
    L4_0_plus_0x100     49.3%  ← 我之前用的，最差
    L5/L6               63.3%

看图 L1 能认出「中 文 宝 可 梦 盘 三 上 / 下 丛 以 合 世 国 界 直」，
与大字页 0 首行完全一致。

⇒ **小字和大字的段布局完全相同**：
      4 段连续 +0x00/+0x10/+0x20/+0x30
      2x2 拼成 16x16
   区别只在 WIDTH 表给的字宽（大字 0x0A/0x0C，小字 8）。

本脚本按此导出，并用字宽裁掉右侧留白。
"""
from __future__ import annotations

import struct
import zlib
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated/宝可梦火红日版汉化2.2.gba").read_bytes()
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
IW261 = (ROOT / "work/_probe/party261/s01_party01_iwram.bin").read_bytes()
BASE = 0x08000000
N = len(zh)
OUT = ROOT / "work" / "_probe" / "smallfont_final2"
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


def glyph16(code: int):
    """4 段连续 + 2x2 -> 16x16（与大字完全相同）。"""
    hi, lo = code >> 8, code & 0xFF
    if hi >= len(PAGES_SMALL):
        return None
    o = PAGES_SMALL[hi] + lo * 64 - BASE
    if o < 0 or o + 64 > N:
        return None
    s = [mat8(decode16(zh[o + k * 16:o + k * 16 + 16])) for k in range(4)]
    return np.vstack([np.hstack([s[0], s[1]]),
                      np.hstack([s[2], s[3]])])


print("=== 导出小字（16x16，4段2x2）===")
items = []
for code in range(MAXCODE + 1):
    m = glyph16(code)
    if m is None:
        continue
    c = Counter(int(v) for v in m.flatten())
    bg = c.most_common(1)[0][0]
    ink = int((m != bg).sum())
    if ink < 8:
        continue
    # 裁掉右侧空白列（小字只有 8 宽）
    keep = 8
    for x in range(15, 7, -1):
        if any(m[y, x] != bg for y in range(16)):
            keep = 16
            break
    items.append((code, m, bg, ink, keep))

print(f"  有内容码位 {len(items)}")
from collections import Counter as C2
print(f"  有效宽度分布: {dict(C2(x[4] for x in items))}")

SCALE = 5
GAP = 4
cols = 24
CW = 16 * SCALE + GAP
CH = 16 * SCALE + GAP


def paint(v: int, bg: int):
    if v == bg:
        return (12, 12, 12)
    return (255, 255, 255) if v > bg else (120, 120, 120)


def render(sel, path: Path, name: str):
    rows = (len(sel) + cols - 1) // cols
    img = np.full((rows * CH, cols * CW, 3), 12, dtype=np.uint8)
    for i, (code, m, bg, ink, keep) in enumerate(sel):
        ry, rx = divmod(i, cols)
        y0 = ry * CH + 2
        x0 = rx * CW + 2
        for y in range(16):
            for x in range(16):
                img[y0 + y * SCALE:y0 + (y + 1) * SCALE,
                    x0 + x * SCALE:x0 + (x + 1) * SCALE] = paint(int(m[y, x]), bg)
    save_png(path, img)
    print(f"  ✔ {name}  ({img.shape[1]}x{img.shape[0]}, {len(sel)} 字)")


render(items, OUT / "SMALL_ALL.png", "SMALL_ALL.png")
for pi in range(11):
    sel = [x for x in items if (x[0] >> 8) == pi]
    if sel:
        render(sel, OUT / f"PAGE{pi:02d}.png", f"PAGE{pi:02d}.png")

arr = np.zeros((len(items), 16, 16), dtype=np.uint8)
for i, (_, m, _, _, _) in enumerate(items):
    arr[i] = m
np.save(OUT / "glyphs.npy", arr)
np.save(OUT / "codes.npy", np.array([c for c, _, _, _, _ in items], dtype=np.int32))
np.save(OUT / "bgs.npy", np.array([b for _, _, b, _, _ in items], dtype=np.uint8))
print(f"\n已存 glyphs.npy {arr.shape}")

print("\n=== 前 8 个字 ===")
for i in range(min(8, len(items))):
    code, m, bg, ink, keep = items[i]
    print(f"\n  码 0x{code:03X} 墨={ink}:")
    for y in range(16):
        print("    " + "".join("." if v == bg else
                               ("#" if v > bg else "+") for v in m[y]))
