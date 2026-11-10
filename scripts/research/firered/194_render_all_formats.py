#!/usr/bin/env python3
"""调研(194) 把 0x08B64A40 的 512 字节按所有常见格式放大渲染，肉眼判断。

═══════════════════════════════════════════════════════════════════════════
【为什么盯住 0x08B64A40】
═══════════════════════════════════════════════════════════════════════════
(192) 反汇编 0x081DB630（字宽判定函数）得到：
    0x081DB630  ldr  r1,[pc,#0x14]      ; r1 = 0x08B64A40
    0x081DB632  subs r1, r4, r1         ; r1 = r4 - 0x08B64A40
    0x081DB634  cmp  r1, #0xa0          ; 与 160 比较
    0x081DB636  bhi  → 返回 12
    0x081DB638  beq  → 返回 2
    0x081DB63A  movs r0,#0xa            ; 否则 10

原版该字面量是 **0x00000000**（即原版是 `subs r1,r4,#0`，r4 直接是字符码）。
汉化把它改成 0x08B64A40 ⇒ **r4 变成了「指向 0x08B64A40 之后某处的指针」**，
按偏移量落在哪一段决定字宽 10 / 2 / 12。

⇒ 0x08B64A40 就是**按字宽分组的字形数据区**：
    偏移 0..159   → 宽 10
    偏移 160      → 宽 2
    偏移 >160     → 宽 12

【本脚本】
 把 0x08B64A40 起 1024 字节按 14 种解释各渲染一张大图：
   4bpp/32B  4bpp/64B  2bpp/16B-row  2bpp/16B-planar  2bpp/32B(8x16)
   1bpp/8B   1bpp/16B  1bpp/32B
   每种再分「正常 / nibble 互换 / 位反转」
 图放大 6 倍，cell 之间留 2px 分隔，便于肉眼识别。

用法：python scripts/research/firered/194_render_all_formats.py
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "fmt194"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
TARGET = 0x08B64A40
LEN = 1024


def save_png(path: Path, arr: np.ndarray) -> None:
    h, w, _ = arr.shape
    raw = b"".join(b"\x00" + arr[y].tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return (struct.pack(">I", len(data)) + c
                + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF))

    path.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9))
                     + chunk(b"IEND", b""))


def bits_to_img(getpix, nw: int, nh: int, n_cells: int,
                cols: int, scale: int, gap: int = 3) -> np.ndarray:
    rows = (n_cells + cols - 1) // cols
    cw = nw * scale + gap
    chh = nh * scale + gap
    img = np.full((rows * chh + gap, cols * cw + gap, 3), 20, dtype=np.uint8)
    for i in range(n_cells):
        ry, rx = divmod(i, cols)
        for y in range(nh):
            for x in range(nw):
                v = getpix(i, y, x)     # 0..255 灰度
                y0 = gap + ry * chh + y * scale
                x0 = gap + rx * cw + x * scale
                img[y0:y0 + scale, x0:x0 + scale] = (v, v, v)
    return img


def nib4(b: bytes, off: int, x: int) -> int:
    v = b[off + (x // 2)]
    return (v & 0x0F) if x % 2 == 0 else (v >> 4)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    zh = ROM_ZH.read_bytes()
    ja = ROM_OR.read_bytes()
    off = TARGET - BASE
    seg = zh[off:off + LEN]

    print(f"目标 0x{TARGET:08X}  取 {LEN} B")
    print(f"原版该区 FF 占 {sum(1 for b in ja[off:off+LEN] if b == 0xFF)}/{LEN}")
    print(f"前 64B: {seg[:64].hex(' ')}")

    made = []

    def emit(name: str, img: np.ndarray) -> None:
        p = OUT / f"{name}.png"
        save_png(p, img)
        made.append((name, img.shape))
        print(f"  ✔ {name:<30} {img.shape[1]}x{img.shape[0]}")

    # ── 4bpp，32 字节 = 8x8 ─────────────────────────────
    n = LEN // 32
    emit("A_4bpp_8x8", bits_to_img(
        lambda i, y, x: nib4(seg, i * 32 + y * 4, x) * 17, 8, 8, n, 16, 6))
    # nibble 互换
    def sw4(i, y, x):
        v = seg[i * 32 + y * 4 + x // 2]
        v = ((v & 0x0F) << 4) | (v >> 4)
        return ((v & 0x0F) if x % 2 == 0 else (v >> 4)) * 17
    emit("B_4bpp_8x8_swapped", bits_to_img(sw4, 8, 8, n, 16, 6))

    # ── 4bpp，64 字节 = 8x16 ────────────────────────────
    n2 = LEN // 64
    emit("C_4bpp_8x16", bits_to_img(
        lambda i, y, x: nib4(seg, i * 64 + y * 4, x) * 17, 8, 16, n2, 12, 6))

    # ── 2bpp，16 字节 = 8x8（每行 2 字节）───────────────
    def p2_row(i, y, x):
        base = i * 16 + y * 2
        v = (seg[base] << 8) | seg[base + 1]
        return ((v >> (14 - x * 2)) & 3) * 85
    emit("D_2bpp_8x8_row", bits_to_img(p2_row, 8, 8, LEN // 16, 16, 6))

    def p2_rowL(i, y, x):
        base = i * 16 + y * 2
        v = seg[base] | (seg[base + 1] << 8)
        return ((v >> (14 - x * 2)) & 3) * 85
    emit("E_2bpp_8x8_rowL", bits_to_img(p2_rowL, 8, 8, LEN // 16, 16, 6))

    # ── 2bpp planar 16 字节 ─────────────────────────────
    def p2_planar(i, y, x):
        base = i * 16
        b0 = seg[base + y]
        b1 = seg[base + 8 + y]
        bit = 7 - x
        v = ((b0 >> bit) & 1) | (((b1 >> bit) & 1) << 1)
        return v * 85
    emit("F_2bpp_8x8_planar", bits_to_img(p2_planar, 8, 8, LEN // 16, 16, 6))

    # ── 2bpp，32 字节 = 8x16 ────────────────────────────
    def p2_8x16(i, y, x):
        base = i * 32 + y * 2
        v = (seg[base] << 8) | seg[base + 1]
        return ((v >> (14 - x * 2)) & 3) * 85
    emit("G_2bpp_8x16_row", bits_to_img(p2_8x16, 8, 16, LEN // 32, 12, 6))

    # ── 1bpp，8 字节 = 8x8 ──────────────────────────────
    def p1_8(i, y, x):
        return ((seg[i * 8 + y] >> (7 - x)) & 1) * 255
    emit("H_1bpp_8x8", bits_to_img(p1_8, 8, 8, LEN // 8, 20, 6))

    # ── 1bpp，16 字节 = 8x16 ────────────────────────────
    def p1_16(i, y, x):
        return ((seg[i * 16 + y] >> (7 - x)) & 1) * 255
    emit("I_1bpp_8x16", bits_to_img(p1_16, 8, 16, LEN // 16, 16, 6))

    # ── 1bpp，32 字节 = 8x32 ────────────────────────────
    def p1_32(i, y, x):
        return ((seg[i * 32 + y] >> (7 - x)) & 1) * 255
    emit("J_1bpp_8x32", bits_to_img(p1_32, 8, 32, LEN // 32, 16, 4))

    # ── 8x8 但按 16 位行、高字节在前（GBA 图标格式）─────
    def icon(i, y, x):
        base = i * 32 + y * 4
        v = (seg[base] << 8) | seg[base + 1]
        return ((v >> (14 - x * 2)) & 3) * 85
    emit("K_icon_2bpp", bits_to_img(icon, 8, 8, LEN // 32, 16, 6))

    # ── 打印前 16 个 4bpp 块的字符画（用 nibble 大小）────
    print("\n前 16 个 32B 块的 nibble 字符画（0-F 原样）：")
    for i in range(16):
        blk = seg[i * 32:(i + 1) * 32]
        print(f"\n  块 {i}  @0x{TARGET + i * 32:08X}")
        for y in range(8):
            row = ""
            for x in range(8):
                row += f"{nib4(blk, y * 4, x):X}"
            print(f"    {row}")

    print(f"\n共生成 {len(made)} 张图，目录 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
