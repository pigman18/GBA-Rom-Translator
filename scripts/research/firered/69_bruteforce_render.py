#!/usr/bin/env python3
"""调研(69) 穷举渲染配置，证明截图与 VRAM 是否同帧、DISPCNT 该是什么。

═══════════════════════════════════════════════════════════════════════════
【为什么这样做】
═══════════════════════════════════════════════════════════════════════════
(68) 拿到同批 shotA.png + A.vram.bin + A.pal.bin + A.io.bin（同帧顺序：先截图后读内存）。
DISPCNT 仍是 0x3140（BG 全关）。

现在用**穷举渲染**判定：
  · 若某个 (mode, charBase, screenBase) 组合能还原 shotA.png
    ⇒ VRAM 是有效的，DISPCNT 的读数才是错的
  · 若无任何组合能还原
    ⇒ 截图与内存不同帧（采集时序），或渲染走了别的路径（OBJ / 特殊模式）

穷举范围：mode 0..5 × charBase(4) × screenBase(32) × 每层
先用 4bpp，再试 8bpp。

相似度判据：逐像素比对「是否同色」，算一致率。

用法：python scripts/research/firered/69_bruteforce_render.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "renderprove"


def load_png_rgb(p: Path) -> np.ndarray:
    """读 PNG 成 (160,240,3) uint8。用 Pillow。"""
    from PIL import Image
    im = Image.open(p).convert("RGB")
    return np.asarray(im, dtype=np.uint8)


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def render_bg(vram: bytes, pal: bytes, char_base: int, screen_base: int,
              bpp8: bool, bg_hoff: int = 0, bg_voff: int = 0) -> np.ndarray:
    """把一层 BG 渲染成 (160,240) 的调色板索引图（0-15 或 0-255）。"""
    out = np.zeros((160, 240), dtype=np.uint8)
    tile_bytes = 64 if bpp8 else 32
    for py in range(160):
        row = (py + bg_voff) // 8
        for px in range(240):
            col = (px + bg_hoff) // 8
            if row >= 32 or col >= 32:
                continue
            ent_off = screen_base + (row * 32 + col) * 2
            if ent_off + 2 > len(vram):
                continue
            ent = rd16(vram, ent_off)
            tidx = ent & 0x3FF
            hflip = (ent >> 10) & 1
            vflip = (ent >> 11) & 1
            pidx = (ent >> 12) & 0xF

            ly = (py + bg_voff) % 8
            lx = (px + bg_hoff) % 8
            if vflip:
                ly = 7 - ly
            if hflip:
                lx = 7 - lx

            toff = char_base + tidx * tile_bytes
            if bpp8:
                if toff + ly * 8 + lx >= len(vram):
                    continue
                out[py, px] = vram[toff + ly * 8 + lx]
            else:
                byte = toff + ly * 4 + lx // 2
                if byte >= len(vram):
                    continue
                b = vram[byte]
                pix = (b & 0x0F) if (lx % 2 == 0) else (b >> 4)
                if pix:
                    out[py, px] = pidx * 16 + pix
    return out


def pal_to_rgb(pal: bytes, idx: np.ndarray, bpp8: bool) -> np.ndarray:
    """调色板索引 → RGB。4bpp 时索引可能带调色板号（0-255），统一按 256 色表处理。"""
    colors = []
    for i in range(256):
        if (i * 2 + 2) <= len(pal):
            v = rd16(pal, i * 2)
        else:
            v = 0
        r = (v & 0x1F) * 255 // 31
        g = ((v >> 5) & 0x1F) * 255 // 31
        b = ((v >> 10) & 0x1F) * 255 // 31
        colors.append((r, g, b))
    colors = np.array(colors, dtype=np.uint8)
    return colors[idx]


def main() -> int:
    vram_p = OUT / "A.vram.bin"
    pal_p = OUT / "A.pal.bin"
    png_p = OUT / "shotA.png"
    io_p = OUT / "A.io.bin"
    for p in (vram_p, pal_p, png_p, io_p):
        if not p.exists():
            print(f"缺少 {p.name}，先跑 68")
            return 1

    vram = vram_p.read_bytes()
    pal = pal_p.read_bytes()
    io = io_p.read_bytes()
    target = load_png_rgb(png_p)

    print("=" * 78)
    print("① 输入")
    print("=" * 78)
    print(f"  VRAM {len(vram):,} B   PAL {len(pal):,} B   PNG {target.shape}")
    print(f"  DISPCNT = 0x{rd16(io, 0):04X}")

    # 目标的主要颜色
    flat = target.reshape(-1, 3)
    uniq, counts = np.unique(flat, axis=0, return_counts=True)
    order = np.argsort(counts)[::-1][:8]
    print(f"\n  截图主要颜色（前 8）：")
    for i in order:
        c = uniq[i]
        print(f"    RGB({c[0]:>3},{c[1]:>3},{c[2]:>3})  "
              f"{counts[i]/len(flat)*100:>5.1f}%")

    # 调色板前 32 色
    print(f"\n  调色板前 32 色：")
    for i in range(0, 32, 8):
        row = []
        for k in range(i, i + 8):
            v = rd16(pal, k * 2)
            r = (v & 0x1F) * 255 // 31
            g = ((v >> 5) & 0x1F) * 255 // 31
            b = ((v >> 10) & 0x1F) * 255 // 31
            row.append(f"({r:>3},{g:>3},{b:>3})")
        print(f"    [{i:>2}-{i+7:>2}] " + " ".join(row))

    # ── ② 穷举 ────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 穷举 (charBase, screenBase, bpp) 还原截图")
    print("=" * 78)
    best = []
    for bpp8 in (False, True):
        for cb in (0, 0x4000, 0x8000, 0xC000):
            if cb >= len(vram):
                continue
            for sb in range(0, 0x8000, 0x800):
                if sb + 0x800 > len(vram):
                    continue
                idx = render_bg(vram, pal, cb, sb, bpp8)
                if idx.max() == 0:
                    continue
                rgb = pal_to_rgb(pal, idx, bpp8)
                # 相似度：像素完全相同的比例
                same = int((rgb == target).all(axis=2).sum())
                rate = same / (240 * 160)
                if rate > 0.10:
                    best.append((rate, cb, sb, bpp8))

    best.sort(reverse=True)
    if best:
        print(f"  找到 {len(best)} 个相似度 >10% 的组合，前 10：")
        for rate, cb, sb, bpp8 in best[:10]:
            print(f"    相似度 {rate:>6.1%}  charBase=0x{cb:04X} "
                  f"screenBase=0x{sb:04X} {'8bpp' if bpp8 else '4bpp'}")
    else:
        print("  **没有任何组合能还原截图**")
        print("  ⇒ VRAM 内容与截图不对应（采集时序 or 走 OBJ/特殊路径）")

    # ── ③ 退一步：只比「颜色集合」是否吻合 ────────────────────────
    print("\n" + "=" * 78)
    print("③ 交叉验证：VRAM 里的 tile 是否与截图颜色吻合")
    print("=" * 78)
    # 统计 VRAM 里出现的像素值分布
    vals = np.zeros(16, dtype=np.int64)
    for k in range(0, len(vram) - 32, 32):
        for byte in vram[k:k + 32]:
            vals[byte & 0x0F] += 1
            vals[byte >> 4] += 1
    print(f"  VRAM 4bpp 像素值分布：{vals.tolist()}")
    print(f"  截图颜色数：{len(uniq)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
