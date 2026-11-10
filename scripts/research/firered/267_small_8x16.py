"""确认小字是 8 宽 × 16 高，导出全量。

═══ 266 的决定性发现 ═══
用**大字的确切逻辑**（swap 读序 + 4 段 + 2x2 拼接）解小字页表，
得到的图案是**真正的汉字**（不是乱码）。

码 0x000：
    .....##.........
    .....##.........
    .##########.....
    .##########.....
    .##..##..##.....
    .##..##..##.....
    .##########.....
    ................
    ....##..........
    ....###..##.....
    ############....
    ############....
    ...##..##.......
    ...##..##.......
    ...######.......
⇒ 上下各 8 行都有效，合起来是 **8 宽 × 16 高**。

而小字配置表 0x08E25F60 里：
    [-3] 0x08B6C000  默认页
    [-2] 0x00000100  段偏移1 = +0x100
    [-1] 0x00000110  段偏移2 = +0x110
    [+0] 0x08002F5D  解码函数

⇒ 小字 = 2 段（+0x00 和 +0x100），每段解 32 字节 = 8x8
   两段纵向拼 = 8 宽 × 16 高
   这与 244 号反汇编的小字分支（宽8、高0x10）**完全吻合**。

═══ 与大字的确切差异（只有一个！）═══
    大字：4 段，偏移 +0x00, +0x10, +0x100, +0x110，2x2 拼 16x16
    小字：2 段，偏移 +0x00, +0x100，**纵向**拼 8x16
    其余（页表结构、index/stride=64、IDX、PAL、decode16）**全部相同**

本脚本按此导出。
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
OUT = ROOT / "work" / "_probe" / "smallfont_ok"
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


def mat8(blob: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


def small_glyph(code: int):
    """小字：2 段（+0x00, +0x100），纵向拼 8x16。"""
    hi, lo = code >> 8, code & 0xFF
    if hi >= len(PAGES_SMALL):
        return None
    a = PAGES_SMALL[hi] + lo * 64
    o = a - BASE
    if o < 0 or o + 64 > N:
        return None
    d0 = mat8(decode16(zh[o:o + 16]))
    o1 = o + 0x100
    if o1 + 16 <= N:
        d1 = mat8(decode16(zh[o1:o1 + 16]))
    else:
        d1 = np.zeros((8, 8), dtype=np.uint8)
    return np.vstack([d0, d1])


# ── 导出 ─────────────────────────────────────────────────
print("=== 导出小字（8x16）===")
items = []
bgs = Counter()
for code in range(MAXCODE + 1):
    m = small_glyph(code)
    if m is None:
        continue
    c = Counter(int(v) for v in m.flatten())
    bg = c.most_common(1)[0][0]
    bgs[bg] += 1
    ink = int((m != bg).sum())
    if ink < 6:
        continue
    items.append((code, m, ink, bg))
print(f"  有内容码位 {len(items)}")
print(f"  背景值分布: {dict(bgs.most_common(5))}")

SCALE = 3
GAP = 2
cols = 32
CW = 8 * SCALE + GAP
CH = 16 * SCALE + GAP


def render(ms, bgl, path: Path, name: str):
    rows = (len(ms) + cols - 1) // cols
    img = np.full((rows * CH, cols * CW, 3), 14, dtype=np.uint8)
    for i, (m, bg) in enumerate(zip(ms, bgl)):
        ry, rx = divmod(i, cols)
        y0 = ry * CH + 1
        x0 = rx * CW + 1
        for y in range(16):
            for x in range(8):
                v = int(m[y, x])
                if v == bg:
                    g = (14, 14, 14)
                elif v in (0,):
                    g = (30, 30, 30)
                else:
                    # 值越大越亮
                    t = min(1.0, max(0.0, (v - 1) / 3.0))
                    gg = int(90 + t * 165)
                    g = (gg, gg, gg)
                img[y0 + y * SCALE:y0 + (y + 1) * SCALE,
                    x0 + x * SCALE:x0 + (x + 1) * SCALE] = g
    save_png(path, img)
    print(f"  ✔ {name}  ({img.shape[1]}x{img.shape[0]}, {len(ms)} 字)")


render([m for _, m, _, _ in items], [b for _, _, _, b in items],
       OUT / "SMALL_ALL.png", "SMALL_ALL.png")

for pi in range(11):
    sel = [(c, m, ink, bg) for c, m, ink, bg in items if (c >> 8) == pi]
    if not sel:
        continue
    render([m for _, m, _, _ in sel], [b for _, _, _, b in sel],
           OUT / f"PAGE{pi:02d}.png", f"PAGE{pi:02d}.png")

arr = np.zeros((len(items), 16, 8), dtype=np.uint8)
for i, (_, m, _, _) in enumerate(items):
    arr[i] = m
np.save(OUT / "glyphs.npy", arr)
np.save(OUT / "codes.npy", np.array([c for c, _, _, _ in items], dtype=np.int32))
np.save(OUT / "bgs.npy", np.array([b for _, _, _, b in items], dtype=np.uint8))
print(f"\n已存 glyphs.npy {arr.shape}")

print("\n=== 前 6 个字 ===")
for i in range(min(6, len(items))):
    code, m, ink, bg = items[i]
    print(f"\n  码 0x{code:03X} 墨={ink} bg=0x{bg:02X}:")
    for y in range(16):
        print("    " + "".join("." if v == bg else
                               ("#" if v > bg else "+") for v in m[y]))
