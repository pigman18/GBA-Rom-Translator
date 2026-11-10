#!/usr/bin/env python3
"""调研(83) 完整渲染验证 + 定位中文字形尺寸。

═══════════════════════════════════════════════════════════════════════════
【突破了】
═══════════════════════════════════════════════════════════════════════════
用 tilemap 表项里的 **pal 字段**（bit12-15）渲染后：
    还原度 从 0.7% 跳到 **37.9%**

调色板 15 的实测颜色：
    [240] RGB(255,255,255)  白
    [241] RGB( 32,131,255)  蓝
    [242] RGB( 98, 98, 98)  **灰 = 文字色**（截图文字区 13.3% 是这个色）

⇒ 之前的失败根因：**我从没按 tilemap 的 pal 字段换调色板**，
  一直用 palette 0 渲染，而文字用的是 palette 15。

═══════════════════════════════════════════════════════════════════════════
【本脚本】
═══════════════════════════════════════════════════════════════════════════
 ① 完整渲染（正确处理每个 tile 的 pal）
 ② 导出渲染结果 PNG，与 g1.png 并排对比
 ③ 找到文字行，量出字形宽度（8 还是 12）

用法：python scripts/research/firered/83_full_render.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "glyphs"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def render_full(vram: bytes, sb: int, cb: int) -> np.ndarray:
    """完整渲染 4bpp BG，正确处理 pal 字段与翻转。"""
    idx = np.zeros((160, 240), dtype=np.uint8)
    for py in range(160):
        row = py // 8
        for px in range(240):
            col = px // 8
            eo = sb + (row * 32 + col) * 2
            if eo + 2 > len(vram):
                continue
            ent = rd16(vram, eo)
            tidx = ent & 0x3FF
            pil = (ent >> 12) & 0xF
            ly, lx = py % 8, px % 8
            if (ent >> 11) & 1:
                ly = 7 - ly
            if (ent >> 10) & 1:
                lx = 7 - lx
            to = cb + tidx * 32
            by = to + ly * 4 + lx // 2
            if by >= len(vram):
                continue
            b = vram[by]
            p = (b & 0x0F) if lx % 2 == 0 else (b >> 4)
            idx[py, px] = (pil * 16 + p) if p else 0
    return idx


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
    print("① 完整渲染并比对")
    print("=" * 78)
    best = None
    for cb in (0, 0x4000, 0x8000, 0xC000):
        for sb in (0xF000, 0xE000, 0x0000 + 0x1000, 0x2000, 0x1800):
            idx = render_full(vram, sb, cb)
            if idx.max() == 0:
                continue
            rgb = to_rgb(pal, idx)
            same = int((rgb == target).all(axis=2).sum())
            rate = same / (240 * 160)
            if best is None or rate > best[0]:
                best = (rate, cb, sb, rgb)
            if rate > 0.10:
                print(f"  char=0x{cb:04X} scr=0x{sb:04X}  还原 {rate:.1%}")

    if best is None:
        print("  全部失败")
        return 1
    rate, cb, sb, rgb = best
    print(f"\n  最佳：char=0x{cb:04X} scr=0x{sb:04X}  还原 {rate:.2%}")

    # 导出对比图
    side = np.concatenate([target, rgb], axis=0)
    Image.fromarray(side).save(OUT / "compare.png")
    Image.fromarray(rgb).save(OUT / "render.png")
    print(f"  已导出 compare.png（上=截图，下=渲染）")

    # ── ② 逐像素差异在哪 ──────────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 差异分布（按 8×8 tile 统计）")
    print("=" * 78)
    diff = ~((rgb == target).all(axis=2))
    print(f"  总差异像素 {diff.sum():,} / {240*160:,} = "
          f"{diff.sum()/(240*160)*100:.1f}%")
    tile_diff = []
    for ty in range(20):
        for tx in range(30):
            n = int(diff[ty * 8:(ty + 1) * 8, tx * 8:(tx + 1) * 8].sum())
            if n > 0:
                tile_diff.append((n, ty, tx))
    tile_diff.sort(reverse=True)
    print(f"  有差异的 tile：{len(tile_diff)}")
    for n, ty, tx in tile_diff[:12]:
        print(f"    tile(行{ty},列{tx}) 差异 {n}/64")

    # ── ③ 文字行定位与字宽测量 ────────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 在渲染结果里找文字行，量字宽")
    print("=" * 78)
    # 文字色是 palette 15 的 index 242（= 15*16+2）
    txt = (np.abs(rgb.astype(int) - np.array([98, 98, 98])).sum(axis=2) < 30)
    rowsum = txt.sum(axis=1)
    print(f"  文字色像素：{txt.sum():,}")
    lines = [y for y in range(160) if rowsum[y] > 5]
    if lines:
        # 分组
        groups = []
        s = p = lines[0]
        for y in lines[1:]:
            if y - p <= 2:
                p = y
            else:
                groups.append((s, p))
                s = p = y
        groups.append((s, p))
        print(f"  文字行带：{len(groups)} 条")
        for a, b in groups[:8]:
            print(f"    y={a}..{b} 高={b-a+1}")
        # 第一条带里量列间距
        a, b = groups[0]
        band = txt[a:b + 1].any(axis=0)
        cols = []
        i = 0
        while i < len(band):
            if band[i]:
                j = i
                while j + 1 < len(band) and band[j + 1]:
                    j += 1
                cols.append((i, j))
                i = j + 1
            else:
                i += 1
        print(f"    该行 {len(cols)} 个笔画段，前 20 个 (起,止,宽):")
        for x0, x1 in cols[:20]:
            print(f"      ({x0:>3},{x1:>3}) 宽={x1-x0+1}")

        # 打印第一行文字带的 ASCII
        print(f"\n  第一条文字带 y={a}..{b} 的 ASCII（x=0..239）：")
        for y in range(a, b + 1):
            line = "".join("#" if txt[y, x] else "." for x in range(240))
            print(f"    {line}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
