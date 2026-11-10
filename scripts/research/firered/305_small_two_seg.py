"""调研(305) 用真实码位 + 两段拼接，验证并导出小字。

═══ 304 的结论 ═══
公式 A `addr = TBL + (code&0xF)*16 + (code>>4)*512` 在真实码位上
确实解出有意义的 8x8 形状（墨 11~23，不是满格）。

═══ 小字函数 0x080062B4 的完整逻辑（280 反汇编）═══
    段1: decode16(addr + 0x00)  -> 0x03003DE0 + 0x00
    段2: decode16(addr + 0x100) -> 0x03003DE0 + 0x40
    宽 = 8，高 = 0x0C

⇒ 输出缓冲布局：
    +0x00..0x20  段1（32B，8x8）
    +0x20..0x40  （空）
    +0x40..0x60  段2（32B，8x8）
  两段各是 8x8，纵向拼 = 8x16，有效 8x12。

本脚本：
 ① 按公式 A 解两段
 ② 纵向拼 8x16
 ③ 与 VRAM 里**有墨**的 tile 比对（排除全背景）
 ④ 命中则导出全量
"""
from __future__ import annotations

import struct
import zlib
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
zh = (ROOT / "roms/translated" / "宝可梦火红日版汉化2.2.gba").read_bytes()
P = ROOT / "work" / "_probe" / "party261"
vr = (P / "s01_party01_vram.bin").read_bytes()
iw = (P / "s01_party01_iwram.bin").read_bytes()
BASE = 0x08000000
N = len(zh)
OUT = ROOT / "work" / "_probe" / "small305"
OUT.mkdir(parents=True, exist_ok=True)

IDX = zh[0x081CDF40 - BASE:0x081CDF40 - BASE + 256]
PAL = iw[0x03000A40 - 0x03000000:0x03000A40 - 0x03000000 + 1024]
TBL = 0x081CEDF4
BG = PAL[0] & 0xF
print(f"背景 nibble = {BG}")


def save_png(path, arr, scale=1):
    if scale > 1:
        arr = np.repeat(np.repeat(arr, scale, axis=0), scale, axis=1)
    h, w, _ = arr.shape
    raw = b"".join(b"\x00" + arr[y].tobytes() for y in range(h))

    def chunk(tag, data):
        c = tag + data
        return (struct.pack('>I', len(data)) + c
                + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF))

    path.write_bytes(b'\x89PNG\r\n\x1a\n'
                     + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(raw, 9))
                     + chunk(b'IEND', b''))


def decode16(src):
    out = bytearray()
    for r3 in range(16):
        p = (r3 // 2) * 2
        v = src[p] if (r3 & 1) else (src[p + 1] if p + 1 < len(src) else 0)
        i = IDX[v]
        off = i * 2
        out += PAL[off:off + 2] if off + 1 < len(PAL) else b'\x00\x00'
    return bytes(out)


def mat8(b):
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            v = b[y * 4 + x // 2]
            m[y, x] = (v & 0xF) if x % 2 == 0 else (v >> 4)
    return m


def addr_of(code):
    return TBL + (code & 0xF) * 16 + (code >> 4) * 512


def small_glyph(code):
    """两段（+0x00 / +0x100）纵向拼 8x16。"""
    a = addr_of(code)
    o = a - BASE
    if o < 0 or o + 0x110 > N:
        return None
    s0 = mat8(decode16(zh[o:o + 16]))
    o1 = o + 0x100
    if o1 + 16 > N:
        return None
    s1 = mat8(decode16(zh[o1:o1 + 16]))
    return np.vstack([s0, s1])


# ── ① 真实码位的两段拼接 ────────────────────────────────
print("\n" + "=" * 78)
print("真实码位 0x00A8 / 0x00BA / 0x00A5 的两段拼接（8x16）")
print("=" * 78)
for code in (0x00A8, 0x00BA, 0x00A5, 0x01AC, 0x010E, 0x0084):
    m = small_glyph(code)
    if m is None:
        print(f"  码 0x{code:03X}: 越界")
        continue
    ink = int((m != BG).sum())
    print(f"\n  码 0x{code:03X} @0x{addr_of(code):08X} 墨={ink}:")
    for y in range(16):
        print("    " + "".join("." if v == BG else "#" for v in m[y]))

# ── ② 与 VRAM 有墨 tile 比对 ─────────────────────────────
print("\n" + "=" * 78)
print("与 VRAM 有墨 tile 比对（排除全背景）")
print("=" * 78)
vr_tiles = {}
for t in range(len(vr) // 32):
    b = vr[t * 32:t * 32 + 32]
    m = mat8(b)
    vals = Counter(int(v) for v in m.flatten())
    bg = vals.most_common(1)[0][0]
    if int((m != bg).sum()) >= 6:
        vr_tiles[t] = b
print(f"  VRAM 有墨 tile: {len(vr_tiles)} 个")

hit_any = 0
for code in range(0x400):
    a = addr_of(code)
    o = a - BASE
    if o < 0 or o + 0x110 > N:
        continue
    d0 = decode16(zh[o:o + 16])
    d1 = decode16(zh[o + 0x100:o + 0x110])
    for t, tgt in vr_tiles.items():
        if d0 == tgt or d1 == tgt:
            hit_any += 1
            if hit_any <= 10:
                print(f"  码 0x{code:03X} 的段 "
                      f"{'0(+0x00)' if d0 == tgt else '1(+0x100)'} "
                      f"== VRAM tile {t}")
            break
print(f"  总命中 {hit_any}")

# ── ③ 导出全量（按码位 0..0x0AFF 试）────────────────────
print("\n" + "=" * 78)
print("导出全量小字")
print("=" * 78)
items = []
for code in range(0, 0x0B00):
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

if items:
    # bbox 统计
    ws, hs = [], []
    for _, m, bg, _ in items[:200]:
        nz = np.argwhere(m != bg)
        if len(nz):
            ws.append(nz[:, 1].max() - nz[:, 1].min() + 1)
            hs.append(nz[:, 0].max() - nz[:, 0].min() + 1)
    print(f"  墨迹宽 均值 {np.mean(ws):.1f}  高 均值 {np.mean(hs):.1f}")

    SCALE = 6
    GAP = 4
    COLS = 16
    PER = 32
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
        print(f"  ✔ {name} ({img.shape[1]}x{img.shape[0]}, {len(sel)} 字)")

    render(items[:PER], OUT / "V_first32.png", "V_first32.png")
    arr = np.zeros((len(items), 16, 8), dtype=np.uint8)
    for i, (_, m, _, _) in enumerate(items):
        arr[i] = m
    np.save(OUT / "glyphs.npy", arr)
    np.save(OUT / "codes.npy", np.array([c for c, _, _, _ in items], dtype=np.int32))
    print(f"  已存 glyphs.npy {arr.shape}")
