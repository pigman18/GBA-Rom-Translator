"""导出火红小字字库（8×8）—— 结构已确证。

═══ 256 的确证（看图确认）════
小字页 0x08B01000 起：
    每字 64 字节（与主字库同 stride）
    只取 **前 16 字节**，经 decode16 -> 32 字节 = 8x8 tile
    渲染结果清晰可读：中 文 宝 可 梦 三 上 下 丛 以 合 包 便 区

═══ 与主字库的关系 ═══
同一批汉字，两种尺寸：
    主字库 PAGES @0x089D08A0 -> 每字 64B，4 段 -> 12x16
    小字库 PAGES @0x08B74000 -> 每字 64B，1 段 -> 8x8
两者页表不同、数据不同，但码位顺序一致（页0 都是「中文宝可梦…」）。

═══ 用法 ═══
python scripts/research/firered/257_small_export_final.py
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
iw = (ROOT / "work/_probe/party232/s05_party_iwram.bin").read_bytes()
vr = (ROOT / "work/_probe/party232/s05_party_vram.bin").read_bytes()
BASE = 0x08000000
N = len(zh)
OUT = ROOT / "work" / "_probe" / "smallfont"
OUT.mkdir(parents=True, exist_ok=True)

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = iw[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]

# 小字页表（配置表 0x08E25F50 指向它）
PAGES_SMALL = [0x08B01000, 0x08B40000, 0x08B50000, 0x08B60000, 0x08B70000,
               0x08B80000, 0x08B90000, 0x08BA0000, 0x08BB0000,
               0x08B64000, 0x08B68000]
DEFAULT_PAGE = 0x08B6C000
MAXCODE = 0x0AFF
STRIDE = 64
SEG_LEN = 16          # 小字只用前 16 字节


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


def mat8(blob32: bytes) -> np.ndarray:
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = blob32[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


def glyph_addr(code: int) -> int | None:
    hi, lo = code >> 8, code & 0xFF
    if hi >= len(PAGES_SMALL):
        return None
    return PAGES_SMALL[hi] + lo * STRIDE


def small_glyph(code: int) -> np.ndarray | None:
    a = glyph_addr(code)
    if a is None:
        return None
    o = a - BASE
    if o < 0 or o + SEG_LEN > N:
        return None
    return mat8(decode16(zh[o:o + SEG_LEN]))


# ── 验证：VRAM 小字 tile 能否在本次解码中找回 ────────────
print("=== 验证：VRAM 里的小字 tile 源自哪个码位 ===")
targets = {t: vr[t * 32:t * 32 + 32]
           for t in (137, 213, 267, 321, 375)}
found = []
for code in range(MAXCODE + 1):
    a = glyph_addr(code)
    if a is None:
        continue
    o = a - BASE
    if o < 0 or o + SEG_LEN > N:
        continue
    d = decode16(zh[o:o + SEG_LEN])
    for t, tgt in targets.items():
        if d == tgt:
            found.append((t, code))
print(f"  命中 {len(found)}: "
      f"{[(t, hex(c)) for t, c in found[:12]]}")

# ── 导出全部码位 ─────────────────────────────────────────
print("\n=== 导出全部码位 ===")
items = []
for code in range(MAXCODE + 1):
    m = small_glyph(code)
    if m is None:
        continue
    # 背景是 PAL[0] 的低/高 nibble，即 0x11；只统计非该值的像素
    ink = int((m != 0x11).sum())
    if ink < 3:
        continue
    items.append((code, m, ink))
print(f"  有内容码位 {len(items)}")

# 值域统计
vals = Counter()
for _, m, _ in items:
    for v in m.flatten():
        vals[int(v)] += 1
print(f"  像素值分布: {dict(sorted(vals.items())[:10])}")

# ── 渲染整张字库 ─────────────────────────────────────────
SCALE = 4
cols = 32
rows = (len(items) + cols - 1) // cols
cw, chh = 8 * SCALE + 2, 8 * SCALE + 2
img = np.full((rows * chh, cols * cw, 3), 14, dtype=np.uint8)
# 背景 0x11 -> 暗，其余按值分级
def lum(v: int) -> tuple[int, int, int]:
    if v == 0x11:
        return (14, 14, 14)
    if v in (0x22, 0x23, 0x32, 0x33):
        return (250, 250, 250)
    return (150, 150, 150)


for i, (code, m, ink) in enumerate(items):
    ry, rx = divmod(i, cols)
    y0 = ry * chh + 1
    x0 = rx * cw + 1
    for y in range(8):
        for x in range(8):
            img[y0 + y * SCALE:y0 + (y + 1) * SCALE,
                x0 + x * SCALE:x0 + (x + 1) * SCALE] = lum(int(m[y, x]))

p = OUT / "SMALL_ALL.png"
save_png(p, img)
print(f"  ✔ {p}  ({img.shape[1]}x{img.shape[0]}, {len(items)} 字)")

# 分页
for pi, pg in enumerate(PAGES_SMALL):
    sel = [(c, m) for c, m, _ in items if (c >> 8) == pi]
    if not sel:
        continue
    r2 = (len(sel) + cols - 1) // cols
    img2 = np.full((r2 * chh, cols * cw, 3), 14, dtype=np.uint8)
    for i, (code, m) in enumerate(sel):
        ry, rx = divmod(i, cols)
        y0 = ry * chh + 1
        x0 = rx * cw + 1
        for y in range(8):
            for x in range(8):
                img2[y0 + y * SCALE:y0 + (y + 1) * SCALE,
                     x0 + x * SCALE:x0 + (x + 1) * SCALE] = lum(int(m[y, x]))
    p2 = OUT / f"PAGE{pi:02d}.png"
    save_png(p2, img2)
    print(f"  ✔ 页{pi} 0x{pg:08X}: {len(sel)} 字 -> {p2.name}")

# 存数组
arr = np.zeros((len(items), 8, 8), dtype=np.uint8)
for i, (_, m, _) in enumerate(items):
    arr[i] = m
np.save(OUT / "glyphs.npy", arr)
np.save(OUT / "codes.npy", np.array([c for c, _, _ in items], dtype=np.int32))
print(f"\n已存 glyphs.npy {arr.shape} / codes.npy")

# 各页在原版的状态
print("\n=== 各页在原版的状态 ===")
for pi, pg in enumerate(PAGES_SMALL):
    o = pg - BASE
    nf = sum(1 for b in ja[o:o + 0x4000] if b == 0xFF)
    print(f"  页{pi} 0x{pg:08X}: 原版 16KB 中 FF={nf} ({nf / 0x4000:.1%})")
