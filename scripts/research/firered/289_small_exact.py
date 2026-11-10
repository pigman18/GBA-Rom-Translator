"""调研(289) 用 0x081DB3EE 的精确公式导出小字。

═══ 288 反汇编逐条确证 ═══
函数 0x081DB3EE（小字，页表 0x08B74000）：

    081DB3F0  movs r4, r0               r4 = code
    081DB3F2  movs r7, r0
    081DB3F4  lsrs r7, r7, #8           r7 = hi
    081DB3F6  cmp  r7, #0xa
    081DB3F8  bhi  0x081DB408           hi > 10 -> 默认页
    081DB3FA  lsls r7, r7, #2           hi * 4
    081DB3FC  ldr  r5, [pc]             0x08B74000  ← 小字页表
    081DB3FE  ldr  r5, [r5, r7]         r5 = PAGES[hi]     ★ 解引用
    081DB410  movs r7, #0xff
    081DB412  ands r4, r7               r4 = lo
    081DB414  lsrs r7, r4, #3           lo >> 3
    081DB416  lsls r7, r7, #9           * 512
    081DB418  movs r4, #7
    081DB41A  ands r4, r0               r4 = code & 7        ★ 用 r0 不是 lo
    081DB41C  lsls r4, r4, #5           * 32
    081DB41E  adds r4, r4, r7           (code&7)*32 + (lo>>3)*512
    081DB420  adds r4, r4, r5           + 页基址
    081DB422  ldr  r6, [pc]             0x03003DE0
    081DB428  bl   0x081DB49C           段 +0x00
    081DB42C  movs r7, #0x10            r7 = 0x10
    081DB42E  adds r0, r4, r7           源 +0x10
    081DB430  movs r7, #0x20
    081DB432  adds r1, r6, r7           目标 +0x20
    081DB434  bl   0x081DB49C           段 +0x10
    081DB438  ldr  r7, [pc]             0x00000100
    081DB43A  adds r0, r4, r7           源 +0x100
    081DB43C  movs r7, #0x40
    081DB43E  adds r1, r6, r7           目标 +0x40
    081DB440  bl   0x081DB49C           段 +0x100
    081DB444  ldr  r7, [pc]             0x00000110
    081DB446  adds r0, r4, r7           源 +0x110
    081DB448  movs r7, #0x60
    081DB44A  adds r1, r6, r7           目标 +0x60
    081DB44C  bl   0x081DB49C           段 +0x110
    081DB450  bl   0x081DB630           取字宽
    081DB454  strb r0, [r1]
    081DB456  movs r0, #0xd
    081DB458  strb r0, [r1, #1]         高 = 0x0D

⇒ 公式：
     addr = PAGES[hi] + (lo >> 3) * 512 + (code & 7) * 32
     4 段：+0x00 / +0x10 / +0x100 / +0x110
     输出：+0x00 / +0x20 / +0x40 / +0x60
     2x2 拼 16x16

⚠ 关键差异（和大字 207 用 0x089D08A0 时相比）：
   我用的是  lo*64             ← 错
   正确是    (lo>>3)*512 + (code&7)*32

   注意 (code&7)*32 里的 code&7 == lo&7（因为 hi 在 bit8+），
   所以 = (lo>>3)*512 + (lo&7)*32
   而 lo*64 = ((lo>>3)*8 + (lo&7))*64 = (lo>>3)*512 + (lo&7)*64
   差别在最后一项的系数：32 vs 64！

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
ja = (ROOT / "roms/origin/POKEMON_FIRE_BPRJ00.gba").read_bytes()
IW261 = (ROOT / "work/_probe/party261/s01_party01_iwram.bin").read_bytes()
BASE = 0x08000000
N = len(zh)
OUT = ROOT / "work" / "_probe" / "smallfont_X"
OUT.mkdir(parents=True, exist_ok=True)

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = IW261[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

PAGES_TBL = 0x08B74000
DEFAULT_PAGE = 0x08B6C000
WIDTH_TBL = 0x081DB6D8 and 0  # 占位，宽度由 0x081DB630 算


def rd32(a):
    o = a - BASE
    return struct.unpack_from('<I', zh, o)[0] if 0 <= o <= N - 4 else None


PAGES = [rd32(PAGES_TBL + k * 4) for k in range(11)]
print("=== 页表 0x08B74000 ===")
for k, p in enumerate(PAGES):
    print(f"  [{k}] 0x{p:08X}")


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
    """addr = PAGES[hi] + (lo>>3)*512 + (code&7)*32，4 段 2x2。"""
    hi, lo = code >> 8, code & 0xFF
    page = PAGES[hi] if hi < len(PAGES) and PAGES[hi] not in (None, 0xFFFFFFFF) else DEFAULT_PAGE
    if page is None:
        return None
    a = page + (lo >> 3) * 512 + (code & 7) * 32
    o = a - BASE
    if o < 0 or o + 0x120 > N:
        return None
    segs = []
    for off in (0x00, 0x10, 0x100, 0x110):
        segs.append(mat8(decode16(zh[o + off:o + off + 16])))
    return np.vstack([np.hstack([segs[0], segs[1]]),
                      np.hstack([segs[2], segs[3]])])


BG = PAL[0] & 0xF
print(f"\n背景 nibble = {BG}")
print("=" * 78)
print("前 8 个码位（字符画）")
print("=" * 78)
for code in range(8):
    m = glyph(code)
    if m is None:
        print(f"  码 0x{code:03X}: 越界")
        continue
    print(f"\n  码 0x{code:03X}:")
    for y in range(16):
        print("    " + "".join("." if v == BG else "#" for v in m[y]))

print("\n" + "=" * 78)
print("全部码位统计")
print("=" * 78)
items = []
for code in range(0x0B00):
    m = glyph(code)
    if m is None:
        continue
    c = Counter(int(v) for v in m.flatten())
    bg = c.most_common(1)[0][0]
    ink = int((m != bg).sum())
    if ink >= 8:
        items.append((code, m, bg, ink))
print(f"  有内容码位 {len(items)}")

if items:
    SCALE = 4
    GAP = 3
    COLS = 16
    CW = 16 * SCALE + GAP
    CH = 16 * SCALE + GAP

    def render(sel, path, name):
        rows = (len(sel) + COLS - 1) // COLS
        img = np.full((rows * CH, COLS * CW, 3), 12, dtype=np.uint8)
        for i, (code, m, bg, ink) in enumerate(sel):
            ry, rx = divmod(i, COLS)
            y0 = ry * CH + 1
            x0 = rx * CW + 1
            for y in range(16):
                for x in range(16):
                    v = int(m[y, x])
                    g = (12, 12, 12) if v == bg else (255, 255, 255)
                    img[y0 + y * SCALE:y0 + (y + 1) * SCALE,
                        x0 + x * SCALE:x0 + (x + 1) * SCALE] = g
        save_png(path, img)
        print(f"  ✔ {name}  ({img.shape[1]}x{img.shape[0]}, {len(sel)} 字)")

    # 小图抽检：每图 32 字
    render(items[:32], OUT / "V_first32.png", "V_first32.png")
    for bi in range(0, len(items), 32):
        render(items[bi:bi + 32], OUT / f"P{bi//32:04d}.png", f"P{bi//32:04d}.png")

    arr = np.zeros((len(items), 16, 16), dtype=np.uint8)
    for i, (_, m, _, _) in enumerate(items):
        arr[i] = m
    np.save(OUT / "glyphs.npy", arr)
    np.save(OUT / "codes.npy", np.array([c for c, _, _, _ in items], dtype=np.int32))
    np.save(OUT / "bgs.npy", np.array([b for _, _, b, _ in items], dtype=np.uint8))
    print(f"\n已存 glyphs.npy {arr.shape}")
