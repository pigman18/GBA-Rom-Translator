#!/usr/bin/env python3
"""调研(82) 定案：用 palette 15 渲染 —— 文字的调色板一直在 tilemap 里。

═══════════════════════════════════════════════════════════════════════════
【破案关键】
═══════════════════════════════════════════════════════════════════════════
(81) 揭示 tilemap（VRAM 0xF000）的真实结构：

    行0:  tile=[0,0,433,434,434,...]  pal=[0,0,2,2,2,...]   ← 边框
    行1:  tile=[0,0,436, 1, 2, 3, 4, 5,...]  **pal=[0,0,2,15,15,15,15,15]**
    行2:  tile=[0,0,436,25,26,27,28,29,...]  pal=[...,15,15,...]
    行3:  tile=[0,0,436,49,50,51,52,53,...]  pal=[...,15,...]

⇒ **文字用调色板 15**，而我一直用调色板 0 渲染！

tile 1 的字节是 `aa aa aa...`，4bpp 下 nibble = 10。
在 palette 15 里，索引 = 15*16 + 10 = **250**。
调色板 0x400 字节 = 256 色，索引 250 在范围内。

⚠ 另一个可能：GBA 4bpp 的调色板选择是 bit12-15，但**有些游戏把
   pal 字段当别的用**。必须直接试。

【本脚本】
 ① 用 tilemap 的真实 pal 字段渲染，与 g1.png 比对
 ② 若还原成功 ⇒ 找到中文字形，可量字宽
 ③ 若失败，退化到「所有 16 个调色板 × 所有 charBase」全组合穷举

用法：python scripts/research/firered/82_palette15.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "glyphs"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def render(vram: bytes, sb: int, cb: int, bpp8: bool,
           use_pal: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """渲染一层，返回 (调色板索引图, 有效掩码)。"""
    idx = np.zeros((160, 240), dtype=np.uint8)
    mask = np.zeros((160, 240), dtype=bool)
    tb = 64 if bpp8 else 32
    for py in range(160):
        row = py // 8
        for px in range(240):
            col = px // 8
            eo = sb + (row * 32 + col) * 2
            if eo + 2 > len(vram):
                continue
            ent = rd16(vram, eo)
            tidx = ent & 0x3FF
            hf, vf = (ent >> 10) & 1, (ent >> 11) & 1
            pil = (ent >> 12) & 0xF
            ly, lx = py % 8, px % 8
            if vf:
                ly = 7 - ly
            if hf:
                lx = 7 - lx
            to = cb + tidx * tb
            if bpp8:
                if to + ly * 8 + lx >= len(vram):
                    continue
                v = vram[to + ly * 8 + lx]
                idx[py, px] = v
                mask[py, px] = v != 0
            else:
                by = to + ly * 4 + lx // 2
                if by >= len(vram):
                    continue
                b = vram[by]
                p = (b & 0x0F) if lx % 2 == 0 else (b >> 4)
                if p:
                    idx[py, px] = (pil * 16 + p) if use_pal else p
                    mask[py, px] = True
    return idx, mask


def to_rgb(pal: bytes, idx: np.ndarray) -> np.ndarray:
    cols = []
    for i in range(256):
        v = rd16(pal, i * 2) if (i * 2 + 2) <= len(pal) else 0
        cols.append(((v & 0x1F) * 255 // 31,
                     ((v >> 5) & 0x1F) * 255 // 31,
                     ((v >> 10) & 0x1F) * 255 // 31))
    return np.array(cols, dtype=np.uint8)[idx]


def main() -> int:
    from PIL import Image

    vram = (OUT / "g1.vram.bin").read_bytes()
    pal = (OUT / "g1.pal.bin").read_bytes()
    target = np.asarray(Image.open(OUT / "g1.png").convert("RGB"),
                        dtype=np.uint8)

    print("=" * 78)
    print("① 调色板 15 里的具体颜色")
    print("=" * 78)
    for base in (0, 2, 15):
        print(f"  palette {base}:")
        for i in range(16):
            v = rd16(pal, (base * 16 + i) * 2)
            r = (v & 0x1F) * 255 // 31
            g = ((v >> 5) & 0x1F) * 255 // 31
            b = ((v >> 10) & 0x1F) * 255 // 31
            print(f"    [{base*16+i:>3}] RGB({r:>3},{g:>3},{b:>3})", end="")
            if i % 3 == 2:
                print()
        print()

    print("=" * 78)
    print("② 用 tilemap 的真实 pal 字段渲染 screenBase=0xF000")
    print("=" * 78)
    best = []
    for use_pal in (True, False):
        for cb in (0, 0x4000, 0x8000, 0xC000):
            idx, mask = render(vram, 0xF000, cb, False, use_pal)
            if mask.sum() == 0:
                continue
            rgb = to_rgb(pal, idx)
            same = int((rgb == target).all(axis=2).sum())
            rate = same / (240 * 160)
            best.append((rate, cb, use_pal, int(mask.sum())))
    best.sort(reverse=True)
    print(f"  {'还原度':>8} {'charBase':>10} {'用pal字段':>9} {'非空像素':>9}")
    for rate, cb, up, npix in best[:8]:
        print(f"  {rate:>7.1%} 0x{cb:04X} {str(up):>9} {npix:>9}")

    # ── ③ 不管还原度，直接把 0xF000 的 tilemap 画出来（pal 15）────
    print("\n" + "=" * 78)
    print("③ 直接画 0xF000 tilemap 的前 12 行（charBase=0，pal 字段生效）")
    print("=" * 78)
    for row in range(12):
        ents = [rd16(vram, 0xF000 + (row * 32 + c) * 2) for c in range(30)]
        tiles = [e & 0x3FF for e in ents]
        pals = [(e >> 12) & 0xF for e in ents]
        if all(t == 0 for t in tiles):
            continue
        print(f"\n  行{row} tiles={tiles[:12]} pal={pals[:12]}")
        for ly in range(8):
            line = ""
            for c in range(30):
                ent = ents[c]
                tidx = ent & 0x3FF
                if tidx == 0:
                    line += " "
                    continue
                to = tidx * 32
                if to + 32 > len(vram):
                    line += "?"
                    continue
                blob = vram[to:to + 32]
                ly2 = 7 - ly if (ent >> 11) & 1 else ly
                rb = blob[ly2 * 4:(ly2 + 1) * 4]
                lx = 3
                b = rb[lx // 2]
                p = (b & 0x0F) if lx % 2 == 0 else (b >> 4)
                line += "." if p == 0 else "#"
            print(f"    |{line}|")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
