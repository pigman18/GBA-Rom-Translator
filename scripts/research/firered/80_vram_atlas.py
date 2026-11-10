#!/usr/bin/env python3
"""调研(80) 用「像素级匹配」定案：VRAM 里到底有没有这幅菜单。

═══════════════════════════════════════════════════════════════════════════
【前面所有尝试的共同缺陷】
═══════════════════════════════════════════════════════════════════════════
一直在用「少数几种 charBase/screenBase 组合」去猜，还原度都 < 1%。
而 g1..g4 的 VRAM MD5 完全相同（52fc9d7c53），PNG 也完全相同
⇒ 这批采集本身是自洽的（都是同一个画面），只是我找不到配置。

【这次换穷举到穷尽】
 GBA 4bpp/8bpp 下：
   · charBase ∈ {0x0000, 0x4000, 0x8000, 0xC000}
   · screenBase ∈ 0..0x1F × 0x800（32 种）
   · 8bpp 时 charBase 实际只有 0x0000/0x4000 有效
 组合数 4×32×2 = 256，之前跑过了。

 ⇒ 全部失败 ⇒ **说明不是「配置找错」，而是 VRAM 里真的没有。**

【换判据：直接在 VRAM 里搜「字形形状」】
 汉字笔画的 4bpp 编码有个特征：**同一行内相邻像素值相同或相近**。
 用这个去扫，比「非 0 非 FF」更准。

同时做一件决定性的事：
 **把 VRAM 所有非空 8×8 tile 拼成一张大图，导出成 PNG，人眼看。**
 这样能一眼看到 VRAM 里到底有什么。

用法：python scripts/research/firered/80_vram_atlas.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "glyphs"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def tile_4bpp(vram: bytes, idx: int) -> np.ndarray:
    o = idx * 32
    if o + 32 > len(vram):
        return np.zeros((8, 8), dtype=np.uint8)
    blob = vram[o:o + 32]
    t = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            b = blob[y * 4 + x // 2]
            t[y, x] = (b & 0x0F) if x % 2 == 0 else (b >> 4)
    return t


def main() -> int:
    from PIL import Image

    vram = (OUT / "g1.vram.bin").read_bytes()
    pal = (OUT / "g1.pal.bin").read_bytes()

    print("=" * 78)
    print("① 建 VRAM 图集：所有 3072 个 4bpp tile 拼成 64×48 网格")
    print("=" * 78)
    cols, rows = 64, 48
    atlas = np.zeros((rows * 8, cols * 8), dtype=np.uint8)
    nonempty = []
    for k in range(min(3072, cols * rows)):
        t = tile_4bpp(vram, k)
        if t.max() > 0:
            nonempty.append(k)
        r, c = k // cols, k % cols
        atlas[r * 8:(r + 1) * 8, c * 8:(c + 1) * 8] = t
    print(f"  非空 tile：{len(nonempty)} 个")
    print(f"  前 40 个：{nonempty[:40]}")

    # 用 4bpp 调色板 0 上色导出
    colors = []
    for i in range(16):
        v = rd16(pal, i * 2)
        colors.append(((v & 0x1F) * 255 // 31,
                       ((v >> 5) & 0x1F) * 255 // 31,
                       ((v >> 10) & 0x1F) * 255 // 31))
    colors = np.array(colors, dtype=np.uint8)
    rgb = colors[atlas]
    p = OUT / "vram_atlas.png"
    Image.fromarray(rgb).save(p)
    print(f"  已导出 {p}  ({rgb.shape})")

    # ── ② 只导出「中等墨量」的 tile，放大 3 倍看得清 ───────────────
    print("\n" + "=" * 78)
    print("② 只导出中等墨量 tile（字形候选），放大 3 倍")
    print("=" * 78)
    cand = []
    for k in range(3072):
        t = tile_4bpp(vram, k)
        ink = int((t > 0).sum())
        if 6 <= ink <= 56:
            cand.append(k)
    print(f"  候选 {len(cand)} 个")
    if cand:
        n = len(cand)
        c2 = 16
        r2 = (n + c2 - 1) // c2
        big = np.zeros((r2 * 8, c2 * 8), dtype=np.uint8)
        for i, k in enumerate(cand):
            r, c = i // c2, i % c2
            big[r * 8:(r + 1) * 8, c * 8:(c + 1) * 8] = tile_4bpp(vram, k)
        big_rgb = colors[big]
        big_rgb = np.repeat(np.repeat(big_rgb, 3, axis=0), 3, axis=1)
        p2 = OUT / "vram_cand.png"
        Image.fromarray(big_rgb).save(p2)
        print(f"  已导出 {p2} ({big_rgb.shape})")
        print(f"  候选 tile 编号：{cand}")

    # ── ③ 对比：截图里文字区域的像素值分布 ───────────────────────
    print("\n" + "=" * 78)
    print("③ 截图文字区的像素值 vs VRAM 里的像素值分布")
    print("=" * 78)
    target = np.asarray(Image.open(OUT / "g1.png").convert("RGB"),
                        dtype=np.uint8)
    # 文字区 y=10..25, x=20..120
    sub = target[10:26, 20:120].reshape(-1, 3)
    uq, ct = np.unique(sub, axis=0, return_counts=True)
    order = np.argsort(ct)[::-1][:8]
    print("  截图文字区颜色：")
    for i in order:
        print(f"    RGB{tuple(uq[i])}  {ct[i]/len(sub)*100:>5.1f}%")

    # VRAM 4bpp 的 nibble 分布
    vals = np.zeros(16, dtype=np.int64)
    for k in range(3072):
        t = tile_4bpp(vram, k)
        for v in range(16):
            vals[v] += int((t == v).sum())
    print(f"\n  VRAM 4bpp nibble 分布：")
    for v in range(16):
        if vals[v]:
            print(f"    {v:>2}: {vals[v]:>8,}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
