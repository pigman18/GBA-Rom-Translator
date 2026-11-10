#!/usr/bin/env python3
"""调研(93) 从「已完整还原的 240×160 画面」切字库 —— 这是最直接的路。

═══════════════════════════════════════════════════════════════════════════
【为什么回到这条路上】
═══════════════════════════════════════════════════════════════════════════
(83) 已经用 palette 15 完整还原了整个画面（compare.png 上下两半一致），
说明「渲染 240×160」这一步是正确的。

后面 (86)-(92) 我又绕回 tilemap 去切，结果全是错位 —— 因为文字是
**整行预渲染进 tile 的**，不是「一个 tile 一个字」，按 tile 边界切必然错。

⇒ 正确做法：在**已还原的 240×160 像素图**上，按实测的
   字宽 11 / 步进 13 / 行高 11 去切。

(85) 已实测：
    文字行带 y=11..21（高 11）
    字起点 x=26, 39, 52, 65（间隔 13）

【本脚本】
 ① 用 palette 15 渲染完整 240×160
 ② 自动找出所有「文字行带」（按灰阶墨迹的 y 分布）
 ③ 每条带内按 13px 步进切字，自动跳过边框（pal=2 的部分）
 ④ 导出干净字库图（行列对齐）+ 每个字的 ASCII

用法：python scripts/research/firered/93_from_rendered.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "glyphs"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def render(vram: bytes, sb: int, cb: int) -> np.ndarray:
    """渲染 4bpp BG，返回 240×160 的 (调色板索引, 是否来自文字调色板)。"""
    idx = np.zeros((160, 240), dtype=np.uint8)
    is_text = np.zeros((160, 240), dtype=bool)
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
            if p:
                idx[py, px] = pil * 16 + p
                is_text[py, px] = (pil == 15)
    return idx, is_text


def main() -> int:
    from PIL import Image

    vram = (OUT / "g1.vram.bin").read_bytes()
    pal = (OUT / "g1.pal.bin").read_bytes()

    idx, is_text = render(vram, 0xF000, 0x0000)

    # 调色板 → RGB
    colors = []
    for i in range(256):
        v = rd16(pal, i * 2) if (i * 2 + 2) <= len(pal) else 0
        colors.append(((v & 0x1F) * 255 // 31,
                       ((v >> 5) & 0x1F) * 255 // 31,
                       ((v >> 10) & 0x1F) * 255 // 31))
    colors = np.array(colors, dtype=np.uint8)

    print("=" * 78)
    print("① 文字像素分布")
    print("=" * 78)
    # 实测：文字 tile 的 nibble 只有 {10, 11, 12}
    #   palette15 下索引 = 240+nibble => 250=白, 251=浅灰, 252=深灰
    #   真正的「笔画」= nibble 11 或 12
    txt = is_text & ((idx % 16 == 11) | (idx % 16 == 12))
    print(f"  笔画像素（nibble 11/12）：{int(txt.sum()):,}")

    rowsum = txt.sum(axis=1)
    lines = [y for y in range(160) if rowsum[y] > 2]
    if not lines:
        print("  没找到文字行")
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
        print(f"    y={a:>3}..{b:<3} 高={b-a+1:<2} 墨 {int(txt[a:b+1].sum()):>4}")

    # ── ② 逐行按 13px 切字 ────────────────────────────────────────
    print("\n" + "=" * 78)
    print("② 按 13px 步进切字")
    print("=" * 78)
    PITCH = 13
    glyphs = []
    for a, b in groups:
        band = txt[a:b + 1]
        W = band.shape[1]
        xsegs = []
        x = 0
        while x + PITCH <= W:
            cell = band[:, x:x + PITCH]
            m = int(cell.sum())
            if m > 3:
                xsegs.append((x, m))
            x += PITCH
        print(f"  带 y={a}..{b}: {len(xsegs)} 个字位  "
              f"x={[s[0] for s in xsegs]}")
        for x0, m in xsegs:
            glyphs.append((a, b, x0, m))

    print(f"\n  合计 {len(glyphs)} 个字位")

    # ── ③ 导出字库 ────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("③ 导出字库")
    print("=" * 78)

    def cell_rgb(a, b, x0):
        """取一个字的 11×13 RGB 块（白底黑字）。"""
        # 只取有墨的行范围
        sub = txt[a:b + 1, x0:x0 + PITCH]
        ys = np.nonzero(sub.any(axis=1))[0]
        if len(ys) == 0:
            h = b - a + 1
        else:
            h = b - a + 1
        c = np.full((h, PITCH, 3), 255, dtype=np.uint8)
        for yy in range(h):
            for xx in range(PITCH):
                gy, gx = a + yy, x0 + xx
                if gy < 160 and gx < 240 and txt[gy, gx]:
                    c[yy, xx] = (0, 0, 0)
        return c

    # 按行带分组导出
    rows = {}
    for a, b, x0, m in glyphs:
        rows.setdefault((a, b), []).append((x0, m))

    row_imgs = []
    for (a, b), items in sorted(rows.items()):
        cells = [cell_rgb(a, b, x0) for x0, m in items]
        if not cells:
            continue
        h = cells[0].shape[0]
        sep = np.full((h, 2, 3), 200, dtype=np.uint8)
        parts = []
        for i, c in enumerate(cells):
            if i:
                parts.append(sep)
            parts.append(c)
        row_imgs.append((a, b, np.concatenate(parts, axis=1)))

    if row_imgs:
        maxw = max(r[2].shape[1] for r in row_imgs)
        pad = 4
        blocks = []
        for a, b, im in row_imgs:
            if im.shape[1] < maxw:
                im = np.hstack([im, np.full((im.shape[0], maxw - im.shape[1],
                                             3), 255, dtype=np.uint8)])
            blocks.append(im)
            blocks.append(np.full((pad, maxw, 3), 180, dtype=np.uint8))
        allimg = np.concatenate(blocks[:-1], axis=0)
        big = np.repeat(np.repeat(allimg, 5, axis=0), 5, axis=1)
        p = OUT / "LIB_glyphs.png"
        Image.fromarray(big).save(p)
        print(f"  → {p.name}  ({big.shape[1]}×{big.shape[0]})")

    # 完整 240×160 也导一份对照
    full = colors[idx]
    Image.fromarray(np.repeat(np.repeat(full, 3, axis=0), 3, axis=1))\
        .save(OUT / "LIB_render_full.png")
    print(f"  → LIB_render_full.png（完整画面，放大 3 倍）")

    # ── ④ ASCII 打印前两条带 ─────────────────────────────────────
    print("\n" + "=" * 78)
    print("④ 前两条带的 ASCII")
    print("=" * 78)
    for a, b in groups[:2]:
        print(f"\n  带 y={a}..{b}:")
        for y in range(a, b + 1):
            line = "".join("#" if txt[y, x] else "." for x in range(0, 150))
            print(f"    {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
