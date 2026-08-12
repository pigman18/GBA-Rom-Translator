#!/usr/bin/env python3
"""把 tiles_patcher 导出的 8x8 图块流拼成可读大图（解决"碎片没法看"）。

用法: python _tile_sheet.py <tiles_dir> <地址前缀> [--cols N] [--out 路径]

例: python _tile_sheet.py work/POKEMON_RUBY_AXVJ00/tiles 0x0836CDA4 --cols 16
    → 把 0x0836CDA4_00..NN.png (8x8) 拼成 16 列网格大图，带 tile 序号标注。
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tiles_dir")
    ap.add_argument("prefix", help="导出地址前缀，如 0x0836CDA4")
    ap.add_argument("--cols", type=int, default=16, help="每行 tile 数")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    d = Path(args.tiles_dir)
    files = sorted(d.glob(f"{args.prefix}_*.png"))
    files = [f for f in files if "palette" not in f.name and "meta" not in f.name]
    if not files:
        print(f"未找到 {args.prefix}_*.png")
        return
    tile = Image.open(files[0])
    tw, th = tile.size
    if tw % 8 or th % 8:
        print(f"仅支持 8 的倍数的图块（当前 {tw}x{th}）")
        return
    cols = args.cols
    rows = (len(files) + cols - 1) // cols
    gap = 2
    label_h = 12
    canvas = Image.new("RGBA", (cols * (tw + gap) + gap, rows * (th + label_h + gap) + gap),
                       (40, 40, 40, 255))
    dr = ImageDraw.Draw(canvas)
    for i, f in enumerate(files):
        r, c = divmod(i, cols)
        x = gap + c * (tw + gap)
        y = gap + r * (th + label_h + gap)
        img = Image.open(f)
        canvas.paste(img, (x, y))
        dr.text((x, y + th + 2), f"{i:02d}", fill=(255, 255, 0))
    out = args.out or str(d / f"{args.prefix}_sheet.png")
    canvas.save(out)
    print(f"拼接 {len(files)} 个 tile → {out} ({canvas.width}x{canvas.height})")


if __name__ == "__main__":
    main()
