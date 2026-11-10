#!/usr/bin/env python3
"""调研(95) 只取深灰笔画 —— 抗锯齿会糊成一片，必须只用核心笔画。

═══════════════════════════════════════════════════════════════════════════
【(94) 的问题】
═══════════════════════════════════════════════════════════════════════════
把 nibble 11（浅灰抗锯齿）和 12（深灰笔画）都当墨，结果每个汉字糊成一团黑色。

参考 GBA 常见做法：字形本体是深色，抗锯齿在外围一圈浅色。
⇒ 只取 **nibble 12** 才是字形骨架。

【本脚本】
 ① 分开统计 nibble 11 与 12 的像素分布
 ② 只用 nibble 12 重建字形，看是否清晰
 ③ 也用「12 为主 + 11 作浅底」两版对比导出

用法：python scripts/research/firered/95_core_strokes.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "glyphs"


def rd16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def render_nib(vram: bytes, sb: int, cb: int) -> np.ndarray:
    """渲染成 240×160 的 (nibble, pal) 两张图。"""
    nib = np.full((160, 240), 10, dtype=np.uint8)
    pal = np.zeros((160, 240), dtype=np.uint8)
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
            nib[py, px] = p
            pal[py, px] = pil
    return nib, pal


def main() -> int:
    from PIL import Image

    vram = (OUT / "g1.vram.bin").read_bytes()
    nib, palmap = render_nib(vram, 0xF000, 0x0000)

    text_zone = palmap == 15

    print("=" * 78)
    print("① 文字区里 nibble 值的分布")
    print("=" * 78)
    from collections import Counter
    c = Counter(nib[text_zone].flatten().tolist())
    for k in sorted(c):
        print(f"  nibble {k:>2}: {c[k]:>7,}")

    core = text_zone & (nib == 12)     # 深灰 = 笔画核心
    anti = text_zone & (nib == 11)     # 浅灰 = 抗锯齿

    print(f"\n  笔画核心（12）：{int(core.sum()):,}")
    print(f"  抗锯齿（11）：  {int(anti.sum()):,}")

    PITCH = 13

    def bands(mask):
        rs = mask.sum(axis=1)
        ls = [y for y in range(160) if rs[y] > 1]
        if not ls:
            return []
        g = []
        s = p = ls[0]
        for y in ls[1:]:
            if y - p <= 2:
                p = y
            else:
                g.append((s, p))
                s = p = y
        g.append((s, p))
        return g

    print("\n" + "=" * 78)
    print("② 用「只有核心笔画」重建，逐行 ASCII")
    print("=" * 78)
    gs = bands(core)
    for a, b in gs:
        print(f"\n  带 y={a}..{b}（高 {b-a+1}）:")
        for y in range(a, b + 1):
            line = ""
            for x in range(20, 140):
                if core[y, x]:
                    line += "#"
                elif anti[y, x]:
                    line += "+"
                else:
                    line += "."
            print(f"    {line}")

    # ── ③ 导出单字网格（核心黑 + 抗锯齿灰）───────────────────────
    print("\n" + "=" * 78)
    print("③ 导出单字网格")
    print("=" * 78)
    glyphs = []
    for a, b in gs:
        x = 0
        while x + PITCH <= 240:
            cm = core[a:b + 1, x:x + PITCH]
            am = anti[a:b + 1, x:x + PITCH]
            if int(cm.sum()) > 2:
                glyphs.append((a, b, x, cm.copy(), am.copy()))
            x += PITCH

    print(f"  共 {len(glyphs)} 个字位")

    if glyphs:
        CH = max(g[3].shape[0] for g in glyphs)
        CW = PITCH
        COLS = 8
        N = len(glyphs)
        ROWS = (N + COLS - 1) // COLS
        GAP = 4
        W = COLS * (CW + GAP) + GAP
        H = ROWS * (CH + GAP) + GAP
        canvas = np.full((H, W, 3), 250, dtype=np.uint8)
        for i, (a, b, x, cm, am) in enumerate(glyphs):
            r, c = i // COLS, i % COLS
            y0 = GAP + r * (CH + GAP)
            x0 = GAP + c * (CW + GAP)
            for yy in range(am.shape[0]):
                for xx in range(am.shape[1]):
                    if am[yy, xx]:
                        canvas[y0 + yy, x0 + xx] = (170, 170, 170)
                    if cm[yy, xx]:
                        canvas[y0 + yy, x0 + xx] = (0, 0, 0)
            canvas[y0 - 1, x0 - 1:x0 + CW + 1] = (150, 150, 200)
            canvas[y0 + CH, x0 - 1:x0 + CW + 1] = (150, 150, 200)
            canvas[y0 - 1:y0 + CH + 1, x0 - 1] = (150, 150, 200)
            canvas[y0 - 1:y0 + CH + 1, x0 + CW] = (150, 150, 200)
        big = np.repeat(np.repeat(canvas, 8, axis=0), 8, axis=1)
        p = OUT / "LIB_GLYPHS_8x.png"
        Image.fromarray(big).save(p)
        print(f"  → {p.name}  ({big.shape[1]}×{big.shape[0]})")

        # 每个字的 ASCII 存文件
        out = []
        for i, (a, b, x, cm, am) in enumerate(glyphs):
            out.append(f"--- #{i} y={a}..{b} x={x} ---")
            for yy in range(cm.shape[0]):
                out.append("".join(
                    "#" if cm[yy, xx] else ("+" if am[yy, xx] else ".")
                    for xx in range(cm.shape[1])))
            out.append("")
        (OUT / "LIB_ascii_core.txt").write_text("\n".join(out),
                                                encoding="utf-8")
        print(f"  → LIB_ascii_core.txt（# 核心笔画，+ 抗锯齿）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
