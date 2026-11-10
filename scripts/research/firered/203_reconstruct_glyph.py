#!/usr/bin/env python3
"""调研(203) 验证真实步进 = 32 字节，并还原 4 次搬运的拼装方式。

═══════════════════════════════════════════════════════════════════════════
【(202) 得到的关键线索】
═══════════════════════════════════════════════════════════════════════════
页 0 @0x08B01000 实际字节：

  lo=0 (offset 0) 64B:
    ffff dbff dbff 55d5 9ada dbdb dbdb 55d5   ← 前 32B
    ffff ffff ffff ff5b ff9b ffdb ffdb ff5b   ← 后 32B
    ff6f ff9b ffff 5555 a9a9 bdfd bdfd 66fe
    ffff ffff ffdb ff56 ffaa ffbf ffbf ffbf

  lo=1 (offset 32) 64B:
    ffff 6fff ff9b ff55 55a9 a9bd fdfd 66fe   ← 前 32B（新）
    ffff ffff ffdb ff56 ffaa ffbf ffbf ffbf   ← 与 lo=0 的后 32B 第 2 段相同

  ⇒ **lo=0 的 offset 32..63 与 lo=1 的 offset 32..63 相同**

这几乎可以断定：**步进是 32 字节**，即
    addr(lo) = 页基址 + (lo>>3)*512 + (lo&7)*32
而每个字形由**多段 32 字节**组成（4 次搬运取 +0x00/+0x10/+0x40/+0x60）。

原版页 0 全 FF ⇒ 汉化用整页 0（64KB）放新增内容。

【本脚本】
 ① 严格验证步进：比较 lo=0..7 各字形的重叠关系，确认是 32 还是 64 步进
 ② 用「4 次搬运」的 4 个偏移拼出字形，试所有可能的排列组合，
    渲染成图，肉眼选能认出汉字的那个
 ③ 检查 0x00/0x10 相差 16 字节 —— 这不是 32 的倍数，
    说明搬运长度可能是 **16 字节**，4 次 = 64 字节，正好一个字形！

  若每次搬 16 字节：
    块0 = addr+0x00 (16B)
    块1 = addr+0x10 (16B)
    块2 = addr+0x40 (16B)
    块3 = addr+0x60 (16B)
    ⇒ 字形 = [0x00:0x10] + [0x10:0x20] + [0x40:0x50] + [0x60:0x70] = 64B
    ⇒ 也就是 offset 0..31 连续（前两块）+ 64..95 连续（后两块）
    ⇒ **字形占 64 字节，中间隔了 32 字节！**

  这解释了为什么 lo=0 和 lo=1 的后半段相同：
    若步进 64，lo=1 在 +64，它的前 32 就是 lo=0 的后 32 —— 与观察一致！

用法：python scripts/research/firered/203_reconstruct_glyph.py
"""
from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "rec203"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_OR = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
PAGE0 = 0x08B01000


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


def nib(blob, off, x):
    v = blob[off + x // 2]
    return (v & 0x0F) if x % 2 == 0 else (v >> 4)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    zh = ROM_ZH.read_bytes()
    ja = ROM_OR.read_bytes()
    o = PAGE0 - BASE
    page = zh[o:o + 0x10000]

    # ── ① 验证步进：lo=0..7 的 64B 重叠关系 ─────────────
    print("=" * 78)
    print("① 步进验证：lo=0..7 各取 offset=(k)*32 处的 64 字节，看重叠")
    print("=" * 78)
    for k in range(8):
        base = k * 32
        blob = page[base:base + 64]
        print(f"  lo={k} offset=0x{base:03X}: {blob[:16].hex(' ')} ... {blob[48:64].hex(' ')}")

    print("\n  lo=0 的 [32:64] vs lo=1 的 [32:64]:")
    print(f"    lo0[32:64] = {page[32:64].hex(' ')}")
    print(f"    lo1[32:64] = {page[32 + 32:32 + 64].hex(' ')}")
    print(f"    相同? {page[32:64] == page[32 + 32:32 + 64]}")
    print("\n  lo=0 的 [64:96] vs lo=1 的 [0:32]:")
    print(f"    lo0[64:96] = {page[64:96].hex(' ')}")
    print(f"    lo1[0:32]  = {page[32:64].hex(' ')}")
    print(f"    相同? {page[64:96] == page[32:64]}")

    # ── ② 试所有拼装方式 ──────────────────────────────
    print("\n" + "=" * 78)
    print("② 4 次搬运（0x00/0x10/0x40/0x60，各 16B）拼出的 64 字节")
    print("=" * 78)
    parts = [page[0x00:0x10], page[0x10:0x20],
             page[0x40:0x50], page[0x60:0x70]]
    glyph64 = b"".join(parts)
    print(f"  拼接结果: {glyph64.hex(' ')}")

    # 也试「连续 64 字节」
    cont64 = page[0:64]
    print(f"  连续 64B : {cont64.hex(' ')}")

    # 试「两块 32B 隔 32B」: [0:32] + [64:96]
    alt = page[0:32] + page[64:96]
    print(f"[0:32]+[64:96]: {alt.hex(' ')}")

    # ── ③ 渲染各种拼法 ────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 渲染候选拼法（8x16，4bpp，值越大越亮）")
    print("=" * 78)

    def render_blob(blob, name, scale=8):
        img = np.full((16 * scale + 2, 8 * scale + 2, 3), 20, dtype=np.uint8)
        for y in range(16):
            for x in range(8):
                v = nib(blob, y * 4, x)
                g = v * 17
                img[1 + y * scale:1 + (y + 1) * scale,
                    1 + x * scale:1 + (x + 1) * scale] = (g, g, g)
        p = OUT / f"{name}.png"
        save_png(p, img)
        print(f"  ✔ {name}")

    render_blob(glyph64, "A_parts_16x4")
    render_blob(cont64, "B_cont64")
    render_blob(alt, "C_0_32_64_96")

    # 也渲染多个连续字形，看是否成篇
    print("\n  渲染 lo=0..7（连续 64B 步进）:")
    cols = 8
    scale = 5
    img = np.full((16 * scale + 4, cols * (8 * scale + 4), 3), 20, dtype=np.uint8)
    for k in range(cols):
        blob = page[k * 64:(k + 1) * 64]
        x0 = k * (8 * scale + 4) + 2
        for y in range(16):
            for x in range(8):
                v = nib(blob, y * 4, x)
                g = v * 17
                img[2 + y * scale:2 + (y + 1) * scale,
                    x0 + x * scale:x0 + (x + 1) * scale] = (g, g, g)
    p = OUT / "D_cont64_8glyphs.png"
    save_png(p, img)
    print(f"  ✔ D_cont64_8glyphs")

    # 32B 步进
    img2 = np.full((16 * scale + 4, cols * (8 * scale + 4), 3), 20, dtype=np.uint8)
    for k in range(cols):
        blob = page[k * 32:k * 32 + 64]
        x0 = k * (8 * scale + 4) + 2
        for y in range(16):
            for x in range(8):
                v = nib(blob, y * 4, x)
                g = v * 17
                img2[2 + y * scale:2 + (y + 1) * scale,
                     x0 + x * scale:x0 + (x + 1) * scale] = (g, g, g)
    p2 = OUT / "E_step32_8glyphs.png"
    save_png(p2, img2)
    print(f"  ✔ E_step32_8glyphs")

    # ── ④ 若 32B = 8x8，两两上下拼 ────────────────────
    print("\n" + "=" * 78)
    print("④ 32B 步进：前 32B 上半、后 32B 下半")
    print("=" * 78)
    scale = 5
    rows, cols2 = 4, 8
    img3 = np.full((rows * (16 * scale + 6), cols2 * (8 * scale + 4), 3),
                   20, dtype=np.uint8)
    for i in range(rows * cols2):
        top = page[i * 32:i * 32 + 32]
        bot = page[i * 32 + 32:i * 32 + 64]
        ry, rx = divmod(i, cols2)
        y0 = ry * (16 * scale + 6) + 2
        x0 = rx * (8 * scale + 4) + 2
        for half, blob in ((0, top), (1, bot)):
            for y in range(8):
                for x in range(8):
                    v = nib(blob, y * 4, x)
                    g = v * 17
                    img3[y0 + (half * 8 + y) * scale:
                         y0 + (half * 8 + y + 1) * scale,
                         x0 + x * scale:x0 + (x + 1) * scale] = (g, g, g)
    p3 = OUT / "F_step32_halves.png"
    save_png(p3, img3)
    print(f"  ✔ F_step32_halves")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
