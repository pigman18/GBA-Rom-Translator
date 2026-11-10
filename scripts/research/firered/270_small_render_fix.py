"""小字最终导出 —— 修正 PNG 渲染的对比度。

═══ 269 的结论 ═══
布局 B（+0x00 和 +0x100，纵向 8x16）**是对的**：
    中 文 宝 可 梦 盘 三 上
    下 丛 以 合 世 国 界 直
与大字页 0 首行完全一致。

═══ 257/267 为什么看起来是糊的 ═══
不是字形错，是**渲染亮度映射错**：
    267: gg = 90 + (v-1)/3 * 165
         => 背景(v=1) = 90（亮灰），笔画 = 145~200
         => 对比度只有 100/255，整张图发糊、像重叠
    269: g = 14 if v == bg else (255 if v > bg else 150)
         => 干净清晰

本脚本用正确映射重出全部图。
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
OUT = ROOT / "work" / "_probe" / "smallfont_v2"
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
    """小字：段 +0x00 与 +0x100，纵向 8x16。"""
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


# ── 导出 ─────────────────────────────────────────────────
print("=== 导出小字（8x16，布局 B）===")
items = []
for code in range(MAXCODE + 1):
    m = small_glyph(code)
    if m is None:
        continue
    bg = Counter(int(v) for v in m.flatten()).most_common(1)[0][0]
    ink = int((m != bg).sum())
    if ink < 6:
        continue
    items.append((code, m, bg, ink))
print(f"  有内容码位 {len(items)}")

SCALE = 4
GAP = 2
cols = 32
CW = 8 * SCALE + GAP
CH = 16 * SCALE + GAP


def paint(v: int, bg: int):
    """正确的三阶灰度：背景最暗，笔画最亮。"""
    if v == bg:
        return (12, 12, 12)
    if v == 0:
        return (26, 26, 26)
    # 值越大越亮（1<2<3）
    t = min(1.0, max(0.0, v / 3.0))
    g = int(110 + t * 145)
    return (g, g, g)


def render(sel, path: Path, name: str):
    rows = (len(sel) + cols - 1) // cols
    img = np.full((rows * CH, cols * CW, 3), 12, dtype=np.uint8)
    for i, (code, m, bg, ink) in enumerate(sel):
        ry, rx = divmod(i, cols)
        y0 = ry * CH + 1
        x0 = rx * CW + 1
        for y in range(16):
            for x in range(8):
                img[y0 + y * SCALE:y0 + (y + 1) * SCALE,
                    x0 + x * SCALE:x0 + (x + 1) * SCALE] = paint(int(m[y, x]), bg)
    save_png(path, img)
    print(f"  ✔ {name}  ({img.shape[1]}x{img.shape[0]}, {len(sel)} 字)")


render(items, OUT / "SMALL_ALL.png", "SMALL_ALL.png")

for pi in range(11):
    sel = [x for x in items if (x[0] >> 8) == pi]
    if sel:
        render(sel, OUT / f"PAGE{pi:02d}.png", f"PAGE{pi:02d}.png")

arr = np.zeros((len(items), 16, 8), dtype=np.uint8)
for i, (_, m, _, _) in enumerate(items):
    arr[i] = m
np.save(OUT / "glyphs.npy", arr)
np.save(OUT / "codes.npy", np.array([c for c, _, _, _ in items], dtype=np.int32))
print(f"\n已存 glyphs.npy {arr.shape}")

# ── 前 8 个字字符画 ──────────────────────────────────────
print("\n=== 前 8 个字 ===")
for i in range(min(8, len(items))):
    code, m, bg, ink = items[i]
    print(f"\n  码 0x{code:03X} 墨={ink}:")
    for y in range(16):
        print("    " + "".join("." if v == bg else
                               ("#" if v > bg else "+") for v in m[y]))

# ── 各页原版状态 ─────────────────────────────────────────
print("\n=== 各页原版 FF 占比 ===")
for pi, pg in enumerate(PAGES_SMALL):
    o = pg - BASE
    nf = sum(1 for b in ja[o:o + 0x4000] if b == 0xFF)
    print(f"  页{pi} 0x{pg:08X}: {nf}/16384 ({nf/0x4000:.1%})")
