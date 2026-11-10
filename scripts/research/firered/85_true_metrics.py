#!/usr/bin/env python3
"""调研(85) 定案：汉字真实尺寸 —— 用「颜色区分」而不是「非零判断」。

═══════════════════════════════════════════════════════════════════════════
【最后的误解】
═══════════════════════════════════════════════════════════════════════════
tile 1 的字节 `aa aa aa...` → nibble=10 → 在 palette 15 里索引 250
palette 15 实测：
    [240] RGB(255,255,255)  ← 索引 0 = 白
    [242] RGB( 98, 98, 98)  ← 索引 2 = **灰字**
    [250] RGB(255,255,255)  ← 索引 10 = **也是白！**

⇒ 「非零 nibble」不等于「有墨」。索引 10 是白色，和索引 0（白）一样看不见。
  必须**按 RGB 颜色判断**，不能按 nibble 是否为零。

这解释了为什么我画出来的都是满格 —— 那是白色。

═══════════════════════════════════════════════════════════════════════════
【正确做法】
═══════════════════════════════════════════════════════════════════════════
 ① 把渲染结果按 RGB 取「非背景色」= 真正的墨
 ② 在墨图上量字宽、步进、行高
 ③ 把单个汉字裁出来，打印成 ASCII，人眼确认是不是汉字

这才能给出「12px 怎么实现」的确切答案。

用法：python scripts/research/firered/85_true_metrics.py
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


def main() -> int:
    from PIL import Image

    vram = (OUT / "g1.vram.bin").read_bytes()
    pal = (OUT / "g1.pal.bin").read_bytes()
    target = np.asarray(Image.open(OUT / "g1.png").convert("RGB"),
                        dtype=np.uint8)

    # 调色板转 RGB 表
    cols = []
    for i in range(256):
        v = rd16(pal, i * 2) if (i * 2 + 2) <= len(pal) else 0
        cols.append(((v & 0x1F) * 255 // 31,
                     ((v >> 5) & 0x1F) * 255 // 31,
                     ((v >> 10) & 0x1F) * 255 // 31))
    cols = np.array(cols, dtype=np.uint8)

    idx = render_full(vram, 0xF000, 0x0000)
    rgb = cols[idx]

    print("=" * 78)
    print("① 渲染结果的真实颜色分布")
    print("=" * 78)
    flat = rgb.reshape(-1, 3)
    uq, ct = np.unique(flat, axis=0, return_counts=True)
    order = np.argsort(ct)[::-1][:8]
    for i in order:
        print(f"  RGB{tuple(uq[i])}  {ct[i]/len(flat)*100:>5.1f}%")

    # ── ② 用「背景色」定义墨 ──────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 定义「墨」= 不是白也不是蓝底")
    print("=" * 78)
    # 白 (255,255,255) 和 蓝 (139,148,255)/(79,83,143) 是背景
    is_white = (rgb[:, :, 0] > 240) & (rgb[:, :, 1] > 240) & \
               (rgb[:, :, 2] > 240)
    print(f"  白色像素 {is_white.sum():,}")

    # 文字灰 (98,98,98)
    is_gray = (np.abs(rgb[:, :, 0].astype(int) - 98) < 40) & \
              (np.abs(rgb[:, :, 1].astype(int) - 98) < 40) & \
              (np.abs(rgb[:, :, 2].astype(int) - 98) < 40)
    print(f"  灰色（文字）像素 {is_gray.sum():,}")

    # ── ③ 在灰字上量尺寸 ──────────────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 灰字墨图的行分布")
    print("=" * 78)
    rowsum = is_gray.sum(axis=1)
    lines = [y for y in range(160) if rowsum[y] > 2]
    if not lines:
        print("  没有灰字像素")
        return 0
    groups = []
    s = p = lines[0]
    for y in lines[1:]:
        if y - p <= 2:
            p = y
        else:
            groups.append((s, p))
            s = p = y
    groups.append((s, p))
    print(f"  文字行带 {len(groups)} 条：")
    for a, b in groups:
        n = int(is_gray[a:b + 1].sum())
        print(f"    y={a:>3}..{b:<3} 高={b-a+1:<3} 墨 {n:>4}")

    # ── ④ 第一行：量字宽与步进 ────────────────────────────────────
    print("\n" + "=" * 78)
    print("④ 第一行文字的列分布（量字宽/步进）")
    print("=" * 78)
    a, b = groups[0]
    band = is_gray[a:b + 1].any(axis=0)
    segs = []
    i = 0
    while i < len(band):
        if band[i]:
            j = i
            while j + 1 < len(band) and band[j + 1]:
                j += 1
            segs.append((i, j))
            i = j + 1
        else:
            i += 1
    print(f"  {len(segs)} 段：")
    for k, (x0, x1) in enumerate(segs):
        advanced = (segs[k + 1][0] - x0) if k + 1 < len(segs) else 0
        print(f"    ({x0:>3},{x1:>3}) 宽={x1-x0+1:<3} "
              f"到下一个起点={advanced}")

    # ── ⑤ 打印第一行 ASCII（灰字）────────────────────────────────
    print("\n" + "=" * 78)
    print("⑤ 第一行文字带 ASCII（x=0..120）")
    print("=" * 78)
    for y in range(a, b + 1):
        line = "".join("#" if is_gray[y, x] else "."
                       for x in range(0, 121))
        print(f"  {y:>3} |{line}|")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
