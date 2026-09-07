#!/usr/bin/env python3
"""TTF → BDF 一次性转换工具（Middle 字库专用，也通用）。

把像素风 TTF（如寒蝉点阵体 ChillBitmap7x）按固定墨迹 cell 渲染成 BDF，
使字体源统一进 build_chinese_font.py 的 BDF 链路（用户拍板 2026-09-07：
不要在构建管线引入 TTF 直渲染，TTF 只在本转换工具里出现一次）。

BDF 规格约定（2026-09-07 用户拍板，与 Normal/Small.bdf 完全一致）：
- FONTBOUNDINGBOX 16 16 0 -2，FONT_ASCENT 14 / FONT_DESCENT 2；
- 每字 BBX 16 16 0 -2，16 行 × 4 位 hex（2 字节/行，低字节=x8..15 恒 00）；
- 墨迹是窄体（默认 ≤8×12），放在 16×16 cell 内 x=0 起、y=TOP_PAD(2) 起，
  左上对齐。bdf_to_ink12 / bdf_to_ink_narrow 均为 bbox 归一化提取，
  墨迹在 cell 内的绝对行位置不影响构建产物，只影响 BDF 查看器显示。

- 墨迹宽 > cell_w 或高 > cell_h → 裁剪并记入 missing 报告；
- charmap 中 TTF 缺字/空白 → 全零行字形 + 报告（bin 里保持空槽）。

用法：
  python scripts/ttf_to_bdf.py --ttf fonts/ChillBitmap7x/ChillBitmap7x.ttf \
      --charmap configs/POKEMON_RUBY_AXVJ00/charmap.txt \
      --out fonts/default/Middle.bdf --cell-w 8 --cell-h 12 --size 8
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_chinese_font import parse_charmap  # noqa: E402

# 16px spec（= Normal/Small.bdf 的头部约定）
SPEC_W, SPEC_H = 16, 16
SPEC_ASCENT, SPEC_DESCENT = 14, 2
TOP_PAD = 2  # 墨迹起始行（视觉上与 slot 的 pad_top=2 一致）


def render_char(char: str, ttf_path: str, size: int, cell_w: int, cell_h: int):
    """渲染单字 → (rows, ink_w, ink_h)；rows 为 1 字节/行的位图（左=高位）。"""
    from PIL import Image, ImageDraw, ImageFont

    margin = 2
    canvas_w, canvas_h = cell_w + margin * 2, cell_h + margin * 2
    font = ImageFont.truetype(ttf_path, size=size)
    img = Image.new("L", (canvas_w, canvas_h), 0)
    ImageDraw.Draw(img).text((margin, margin), char, font=font, fill=255)

    xs, ys = [], []
    for y in range(canvas_h):
        for x in range(canvas_w):
            if img.getpixel((x, y)) >= 96:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None, 0, 0  # TTF 无此字（空白字形）

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    ink_w = max_x - min_x + 1
    ink_h = max_y - min_y + 1
    ink_w = min(ink_w, cell_w)
    ink_h = min(ink_h, cell_h)

    rows = [0] * ink_h
    for y in range(ink_h):
        for x in range(ink_w):
            if img.getpixel((min_x + x, min_y + y)) >= 96:
                rows[y] |= 0x80 >> x
    return rows, ink_w, ink_h


def main() -> None:
    ap = argparse.ArgumentParser(description="Pixel TTF → BDF (16px spec, narrow ink)")
    ap.add_argument("--ttf", required=True)
    ap.add_argument("--charmap", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--cell-w", type=int, default=8,
                    help="墨迹最大宽（窄体=8）")
    ap.add_argument("--cell-h", type=int, default=12,
                    help="墨迹最大高（12px 行网格=12）")
    ap.add_argument("--size", type=int, default=None,
                    help="PIL 渲染 pt；默认 = cell_w（寒蝉 7px 用 8）")
    args = ap.parse_args()

    size = args.size if args.size is not None else args.cell_w
    charmap = parse_charmap(args.charmap)
    chars = sorted(set(charmap.values()))
    print(f"charmap unique chars: {len(chars)}")

    empty_chars: list[str] = []
    clipped_chars: list[str] = []
    glyphs: list[tuple[int, str, list[str]]] = []  # (encoding, name, hex_rows)

    for ch in chars:
        enc = ord(ch)
        name = f"uni{enc:04X}"
        rows, ink_w, ink_h = render_char(ch, args.ttf, size, args.cell_w, args.cell_h)
        if rows is None:
            empty_chars.append(ch)
            rows, ink_w, ink_h = [], 0, 0
        if ink_w > args.cell_w or ink_h > args.cell_h:
            clipped_chars.append(ch)

        # 16×16 cell：墨迹放 x0..、y=TOP_PAD..，低字节（x8..15）恒 00
        hex_rows = ["0000"] * SPEC_H
        for y, r in enumerate(rows[: SPEC_H - TOP_PAD]):
            hex_rows[TOP_PAD + y] = f"{r:02X}00"
        glyphs.append((enc, name, hex_rows))

    lines = [
        "STARTFONT 2.1",
        "FONT -Middle-Medium-R-Normal--%d-%d-75-75-P-40-ISO10646-1"
        % (SPEC_H, SPEC_H * 10),
        "SIZE %d 75 75" % SPEC_H,
        "FONTBOUNDINGBOX %d %d 0 %d" % (SPEC_W, SPEC_H, -SPEC_DESCENT),
        "STARTPROPERTIES 5",
        "FONT_ASCENT %d" % SPEC_ASCENT,
        "FONT_DESCENT %d" % SPEC_DESCENT,
        "DEFAULT_CHAR 0",
        "PIXEL_SIZE %d" % SPEC_H,
        'COMMENT "TTF->BDF by scripts/ttf_to_bdf.py; 16px spec, narrow ink top-left"',
        "ENDPROPERTIES",
        "CHARS %d" % len(glyphs),
    ]
    for enc, name, hex_rows in glyphs:
        lines += [
            f"STARTCHAR {name}",
            f"ENCODING {enc}",
            "SWIDTH 100 0",
            "DWIDTH 10 0",
            f"BBX {SPEC_W} {SPEC_H} 0 {-SPEC_DESCENT}",
            "BITMAP",
            *hex_rows,
            "ENDCHAR",
        ]
    lines.append("ENDFONT")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="ascii")
    print(f"written {len(glyphs)} glyphs -> {args.out} (16px spec, ink {args.cell_w}x{args.cell_h} @row{TOP_PAD})")
    if clipped_chars:
        print(f"⚠ 超出 {args.cell_w}x{args.cell_h} 被裁剪 {len(clipped_chars)} 字: "
              + "".join(clipped_chars[:60]))
    if empty_chars:
        print(f"TTF 缺字(空槽) {len(empty_chars)} 字: "
              + "".join(empty_chars[:60]) + ("..." if len(empty_chars) > 60 else ""))


if __name__ == "__main__":
    main()
