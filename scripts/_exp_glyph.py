"""10px 点阵化策略对比实验（临时脚本，不属于构建链路）。

目的：验证「有 hinting 的字体在 10px 下能否出可用点阵」。
之前只试过 Noto Sans SC（hinting 弱）就断定 10px 不可行，这里把
FreeType 的几档 hinting / 二值化策略并排渲染，肉眼看差距。

用法:
    python scripts/_exp_glyph.py --px 10 --out work/font_preview/exp10.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import freetype
from PIL import Image, ImageDraw

FONTS = [
    (r"C:\Windows\Fonts\simsun.ttc", 0, "SimSun"),
    (r"C:\Windows\Fonts\msyh.ttc", 0, "YaHei"),
]

CHARS = "学习装置单项小补剂活力好伤先制之爪奇迹种子蘑菇丝绸围巾酱繁"


def _to_img(bmp, invert: bool = True) -> Image.Image | None:
    if bmp.width <= 0 or bmp.rows <= 0:
        return None
    buf = bytes(bmp.buffer)
    mode = bmp.pixel_mode
    if mode == freetype.FT_PIXEL_MODE_MONO:
        img = Image.new("L", (bmp.width, bmp.rows), 255)
        px = img.load()
        for y in range(bmp.rows):
            row = buf[y * bmp.pitch:(y + 1) * bmp.pitch]
            for x in range(bmp.width):
                if (x >> 3) < len(row) and (row[x >> 3] & (0x80 >> (x & 7))):
                    px[x, y] = 0
        return img
    if mode == freetype.FT_PIXEL_MODE_GRAY:
        return Image.frombytes("L", (bmp.width, bmp.rows), buf)
    return None


def render(face, ch: str, px: int, flags: int) -> Image.Image | None:
    try:
        face.set_char_size(0, px * 64, 72, 72)
        face.load_char(ch, flags)
    except Exception:
        return None
    return _to_img(face.glyph.bitmap)


def render_ss(face, ch: str, px: int, ss: int, cov: float) -> Image.Image | None:
    """超采样灰度 -> BOX 面积平均 -> 覆盖率阈值。"""
    g = render(face, ch, px * ss, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL)
    if g is None:
        return None
    w = max(1, round(g.width / ss))
    h = max(1, round(g.height / ss))
    small = g.resize((w, h), Image.Resampling.BOX)
    t = round(255 * cov)
    return small.point(lambda v: 0 if v >= t else 255)


STRATS = [
    ("mono+bc", lambda f, c, px: render(f, c, px,
        freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO | freetype.FT_LOAD_NO_AUTOHINT)),
    ("mono+auto", lambda f, c, px: render(f, c, px,
        freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO | freetype.FT_LOAD_FORCE_AUTOHINT)),
    ("gray128", lambda f, c, px: (lambda g: g.point(lambda v: 0 if v >= 128 else 255) if g else None)(
        render(f, c, px, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL | freetype.FT_LOAD_NO_AUTOHINT))),
    ("gray80", lambda f, c, px: (lambda g: g.point(lambda v: 0 if v >= 80 else 255) if g else None)(
        render(f, c, px, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL | freetype.FT_LOAD_NO_AUTOHINT))),
    ("ss4@.30", lambda f, c, px: render_ss(f, c, px, 4, 0.30)),
    ("ss8@.35", lambda f, c, px: render_ss(f, c, px, 8, 0.35)),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--px", type=int, default=10)
    ap.add_argument("--out", default="work/font_preview/exp.png")
    ap.add_argument("--zoom", type=int, default=8)
    a = ap.parse_args()

    cell = a.px + 2
    z = a.zoom
    rows = []
    for path, idx, name in FONTS:
        if not Path(path).exists():
            print("missing", path, file=sys.stderr)
            continue
        face = freetype.Face(path, index=idx)
        for sname, fn in STRATS:
            tiles = []
            for ch in CHARS:
                g = fn(face, ch, a.px)
                if g is None:
                    g = Image.new("L", (a.px, a.px), 255)
                tiles.append(g)
            rows.append((f"{name} {a.px}px {sname}", tiles))

    cols = len(CHARS)
    W = cols * cell * z + 140
    H = len(rows) * cell * z
    img = Image.new("RGB", (W, H), (255, 255, 255))
    dr = ImageDraw.Draw(img)

    for r, (label, tiles) in enumerate(rows):
        y0 = r * cell * z
        dr.text((6, y0 + cell * z // 2 - 5), label, fill=(0, 0, 0))
        x = 140
        for g in tiles:
            # 底对齐放置（汉字基线大致一致），多出的高度向上溢出
            gh, gw = g.height, g.width
            tile = Image.new("L", (cell, cell), 255)
            ox = (cell - gw) // 2
            oy = cell - 1 - gh
            if oy < 0:
                g = g.crop((0, -oy, gw, gh))
                oy = 0
            tile.paste(g, (max(0, ox), oy))
            big = tile.resize((cell * z, cell * z), Image.Resampling.NEAREST)
            img.paste(big.convert("RGB"), (x, y0))
            x += cell * z
        dr.line([(0, y0), (W, y0)], fill=(220, 220, 220))

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"wrote {out}  ({img.width}x{img.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
