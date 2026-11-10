#!/usr/bin/env python3
"""调研(202) 确定字形数据的真实位深与排列 —— 反推 4 次搬运的含义。

═══════════════════════════════════════════════════════════════════════════
【(201) 已确证的结构】
═══════════════════════════════════════════════════════════════════════════
页表 @0x08B74000，11 项：
  汉化: 0x08B01000, 0x08B40000, 0x08B50000, ..., 0x08BB0000,
        0x08B64000, 0x08B68000        ← 共 11 页，对应 hi = 0x00..0x0A
  原版: 0x08B40000, 0x08B50000, ..., 0x08BB0000,
        0x08B64000, 0x08B68000        ← 只有 10 页，第 0 项原本是 0x08B40000

⇒ **原版就有这套页式字库，汉化插入了新的一页。**

地址公式（已确证）：
  offset = (lo>>3)*512 + (lo&7)*32
  addr   = 页基址 + offset

4 次搬运（0x081DB428 / 434 / 440 / 44C）：
  r0 = 字形地址 + 0x00, r1 = 目标 + 0x00
  r0 = 字形地址 + 0x10, r1 = 目标 + 0x20
  r0 = 字形地址 + 0x40, r1 = 目标 + 0x40
  r0 = 字形地址 + 0x60, r1 = 目标 + 0x60

**但 (201) 按「64 字节 = 8x16 4bpp」渲染出来全是未知 nibble（图全红）**
⇒ 真实编码不是 10/11/12 的 4bpp。

【本脚本】
 ① dump 一页开头 512 字节的原始十六进制
 ② 统计整页 nibble/byte 分布（值域是什么）
 ③ 按 4 次搬运的实际偏移（0x00/0x10/0x40/0x60，长度各 32）
    重组一个字形，看拼出来是什么
 ④ 试 10 种位深/排列，各渲染一张小图，肉眼选对的
 ⑤ 若找到正确格式，重新导出整张字库

【关键：4 次搬运的偏移差是 0x10 / 0x30 / 0x20】
  若每块 32 字节，则 4 块覆盖 [0,0x20) [0x10,0x30) [0x40,0x60) [0x60,0x80)
  → 第一二块重叠！说明我读错了长度，需要从 0x081DB49C 的真实实现确认。

用法：python scripts/research/firered/202_find_glyph_encoding.py
"""
from __future__ import annotations

import json
import struct
import zlib
from collections import Counter
from pathlib import Path

import numpy as np
from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "enc202"
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


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    zh = ROM_ZH.read_bytes()
    ja = ROM_OR.read_bytes()

    o = PAGE0 - BASE
    seg = zh[o:o + 512]

    # ── ① 原始十六进制 ───────────────────────────────
    print("=" * 78)
    print(f"① 页 0 @0x{PAGE0:08X} 开头 256 字节")
    print("=" * 78)
    for i in range(0, 256, 16):
        row = seg[i:i + 16]
        print(f"  +{i:03X}  {' '.join(f'{b:02x}' for b in row)}")

    # ── ② nibble / byte 分布 ──────────────────────────
    print("\n" + "=" * 78)
    print("② 整页 64KB 的值分布")
    print("=" * 78)
    page = zh[o:o + 0x10000]
    nib = Counter()
    for b in page:
        nib[b & 0x0F] += 1
        nib[b >> 4] += 1
    tot = sum(nib.values())
    print("  nibble 分布：")
    for v in sorted(nib):
        print(f"    {v:X}: {nib[v]:>7,}  ({nib[v] / tot:>6.2%})")
    bcnt = Counter(page)
    print(f"  byte 种类：{len(bcnt)}")
    print(f"  最常见 byte：{[(f'0x{v:02X}', n) for v, n in bcnt.most_common(10)]}")

    # ── ③ 按 4 次搬运重组 ─────────────────────────────
    print("\n" + "=" * 78)
    print("③ 4 次搬运的含义（从 0x081DB49C 实现看）")
    print("=" * 78)
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    # 0x081DB49C 是个 thunk：ldr r3,[pc]; bx r3
    off4 = 0x081DB49C - BASE
    thunk_target = struct.unpack_from("<I", zh, 0x081DB4A0 - BASE)[0]
    print(f"  0x081DB49C: ldr r3,[pc,#0x1c] ; bx r3")
    print(f"  字面量 @0x081DB4A0 = 0x{thunk_target:08X}")
    if BASE <= thunk_target < BASE + len(zh):
        print(f"\n  实际搬运函数 0x{thunk_target:08X}:")
        for ins in md.disasm(zh[thunk_target - BASE:
                                thunk_target - BASE + 0x80], thunk_target):
            raw = zh[ins.address - BASE:ins.address - BASE + ins.size]
            print(f"    0x{ins.address:08X}  {raw.hex():<8} "
                  f"{ins.mnemonic:<8} {ins.op_str}")

    # ── ④ 试 10 种格式渲染 ────────────────────────────
    print("\n" + "=" * 78)
    print("④ 用第一个字形位置试 10 种格式")
    print("=" * 78)
    # 第一个字形：lo=0 → offset=0
    g0 = zh[o:o + 0x80]

    def render(fn, w, h, name, scale=6, n=4):
        cols = n
        cw, chh = w * scale + 3, h * scale + 3
        img = np.full((chh, cols * cw, 3), 20, dtype=np.uint8)
        for i in range(n):
            x0 = i * cw + 1
            for y in range(h):
                for x in range(w):
                    v = fn(i, y, x)
                    g = max(0, min(255, int(v)))
                    img[1 + y * scale:1 + (y + 1) * scale,
                        x0 + x * scale:x0 + (x + 1) * scale] = (g, g, g)
        p = OUT / f"{name}.png"
        save_png(p, img)
        print(f"  ✔ {name:<22} {img.shape[1]}x{img.shape[0]}")

    def nib_at(blob, off, x):
        v = blob[off + x // 2]
        return (v & 0x0F) if x % 2 == 0 else (v >> 4)

    # 每个字形 64 字节（8x8 x2），4bpp 直读
    render(lambda i, y, x: nib_at(g0, i * 64 + y * 4, x) * 17,
           8, 16, "F1_4bpp_8x16")

    # 4bpp，但 nibble 互换
    def sw(i, y, x):
        v = g0[i * 64 + y * 4 + x // 2]
        v = ((v & 0x0F) << 4) | (v >> 4)
        return ((v & 0x0F) if x % 2 == 0 else (v >> 4)) * 17
    render(sw, 8, 16, "F2_4bpp_swapped")

    # 2bpp 16 字节 x 4
    def p2(i, y, x):
        base = i * 32 + y * 2
        v = (g0[base] << 8) | g0[base + 1]
        return ((v >> (14 - x * 2)) & 3) * 85
    render(p2, 8, 16, "F3_2bpp_8x16")

    # 1bpp 16 字节
    def p1(i, y, x):
        return ((g0[i * 16 + y] >> (7 - x)) & 1) * 255
    render(p1, 8, 16, "F4_1bpp_8x16")

    # 1bpp 32 字节（8x32）
    def p1b(i, y, x):
        return ((g0[i * 32 + y] >> (7 - x)) & 1) * 255
    render(p1b, 8, 32, "F5_1bpp_8x32", scale=4, n=2)

    # 按 4 次搬运重组：4 块 32B 分别放到 4 个象限
    def quad(i, y, x):
        # 上半 = 块0(0x00)，下半 = 块1(0x10)? 用实际偏移
        offs = [0x00, 0x10, 0x40, 0x60]
        if y < 8:
            base = i * 64 + offs[0]
        else:
            base = i * 64 + offs[1]
        yy = y % 8
        return nib_at(g0, base + yy * 4, x) * 17
    render(quad, 8, 16, "F6_quad_0_10")

    # 4 块当 2x2 tile
    def quad2(i, y, x):
        offs = [0x00, 0x10, 0x40, 0x60]
        blk = (0 if y < 8 else 2) + (0 if x < 4 else 1)
        base = i * 64 + offs[blk]
        return nib_at(g0, base, (y % 8) * 4, x % 4) * 17
    render(quad2, 8, 16, "F7_quad_2x2", scale=6, n=2)

    # 每 32B 是一个 8x8 4bpp，连续画 4 个
    for k in range(2):
        def mk(i, y, x, kk=k):
            return nib_at(g0, (i * 2 + kk) * 32 + y * 4, x) * 17
        render(mk, 8, 8, f"F8_tile{k}_8x8")

    # ── ⑤ 关键：对比原版同页 ──────────────────────────
    print("\n" + "=" * 78)
    print("⑤ 对比原版页 0（原版页表[0] = 0x08B40000）")
    print("=" * 78)
    for name, addr in (("汉化页0", PAGE0), ("原版页0", 0x08B40000)):
        oo = addr - BASE
        s = zh[oo:oo + 64] if addr != 0x08B40000 else ja[oo:oo + 64]
        src = "汉化" if addr != 0x08B40000 else "原版"
        print(f"  {name} @0x{addr:08X}（取自{src}）:")
        print(f"    {s.hex(' ')}")

    (OUT / "info.json").write_text(
        json.dumps({"page0": PAGE0,
                    "nib_hist": {f"{k:X}": v for k, v in sorted(nib.items())}},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
