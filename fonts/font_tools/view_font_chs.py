#!/usr/bin/env python3
"""
view_font_chs.py
=============
Read a Gen3 Chinese font .bin laid out as:
    N glyphs × 128 bytes/glyph
    128B = TL(32) + BL(32) + TR(32) + BR(32)
    Each 32B = one 8x8 4bpp tile (left pixel = high nibble)
For each glyph, reassemble the full 16x16 4bpp image and:
    - Print a 16x16 ASCII preview (nibble→char) to terminal
    - Save a grayscale PNG so you can eye-check the shape
Usage:
    python3 view_font_chs.py font.bin [--index 0] [--count 16] [--out out.png]
Defaults: shows glyph 0..15 as a 4x4 grid PNG, plus ASCII for glyph 0.
"""

import struct, argparse, sys
from PIL import Image, ImageDraw, ImageFont

# 4bpp nibble → ASCII for terminal preview
NIBBLE_TO_CHAR = ".", "-", "o", "x", "X", "#", "@", "%", "&", "*", "+", "=", "~", "^", "█", "■"

def nibble_of(tile32: bytes, x: int, y: int) -> int:
    """tile32 = 32 bytes of one 8x8 4bpp tile. x,y in 0..7. Returns 0..15."""
    bi = y * 4 + x // 2
    if x & 1:
        return tile32[bi] & 0x0F
    return (tile32[bi] >> 4) & 0x0F

def glyph_to_image(data128: bytes) -> Image.Image:
    """Take 128 bytes (TL,BL,TR,BR) and return a 16x16 grayscale PIL image."""
    tl = data128[0x00:0x20]
    bl = data128[0x20:0x40]
    tr = data128[0x40:0x60]
    br = data128[0x60:0x80]

    img = Image.new("L", (16, 16), 0)
    # Top-left
    for y in range(8):
        for x in range(8):
            n = nibble_of(tl, x, y)
            img.putpixel((x, y), n * 17)  # 0..15 → 0..255
    # Bottom-left
    for y in range(8):
        for x in range(8):
            n = nibble_of(bl, x, y)
            img.putpixel((x, y + 8), n * 17)
    # Top-right
    for y in range(8):
        for x in range(8):
            n = nibble_of(tr, x, y)
            img.putpixel((x + 8, y), n * 17)
    # Bottom-right
    for y in range(8):
        for x in range(8):
            n = nibble_of(br, x, y)
            img.putpixel((x + 8, y + 8), n * 17)
    return img

def glyph_to_ascii(data128: bytes) -> str:
    lines = []
    for row in range(16):
        if row < 8:
            tile = data128[0x00:0x20] if row < 8 else data128[0x20:0x40]
            y_in_tile = row
        else:
            tile = data128[0x20:0x40] if row < 16 else data128[0x60:0x80]
            y_in_tile = row - 8 if row < 16 else row - 16
        # We rebuild per-row from the right tile
        # Top half
        pass
    # Simpler: just iterate all 16x16
    out = []
    # Pre-extract tiles
    tl = data128[0x00:0x20]; bl = data128[0x20:0x40]
    tr = data128[0x40:0x60]; br = data128[0x60:0x80]
    for row in range(16):
        line = []
        for col in range(16):
            if row < 8 and col < 8:
                n = nibble_of(tl, col, row)
            elif row < 8 and col >= 8:
                n = nibble_of(tr, col - 8, row)
            elif row >= 8 and col < 8:
                n = nibble_of(bl, col, row - 8)
            else:
                n = nibble_of(br, col - 8, row - 8)
            line.append(NIBBLE_TO_CHAR[n])
        out.append("".join(line))
    return "\n".join(out)

def main():
    ap = argparse.ArgumentParser(description="Preview a Gen3 128B/glyph Chinese font .bin")
    ap.add_argument("bin", help="Path to font .bin (128B × N glyphs, TL/BL/TR/BR 4bpp)")
    ap.add_argument("--index", type=int, default=0, help="First glyph index to show")
    ap.add_argument("--count", type=int, default=16, help="How many glyphs to dump")
    ap.add_argument("--out", default="font_preview.png", help="Output PNG grid path")
    ap.add_argument("--cols", type=int, default=4, help="Grid columns in PNG")
    args = ap.parse_args()

    with open(args.bin, "rb") as f:
        data = f.read()

    total = len(data) // 128
    print(f"File: {args.bin}")
    print(f"Total glyphs: {total}  ({len(data)} bytes)")
    if total == 0:
        print("ERROR: file too small, not a 128B/glyph font"); sys.exit(1)

    end = min(args.index + args.count, total)
    # ASCII preview of first requested glyph
    first = data[args.index*128:(args.index+1)*128]
    print(f"\n--- ASCII preview of glyph #{args.index} (bytes 0x00..0x7F) ---")
    print(glyph_to_ascii(first))
    print("Legend: . = 0(透明)  █ = 15(墨)  数字/符号 = 中间色(阴影)")
    print("Expected for an inked 12px glyph: rows 2-13 have █/heavy chars,")
    print("rows 0-1 and 14-15 are '.' (padding). Left/right 4 cols may also be '.'.")

    # Build grid PNG
    cols = args.cols
    rows = (args.count + cols - 1) // cols
    cell = 16 * 4  # each glyph rendered at 4x scale
    grid = Image.new("L", (cols * cell + (cols+1)*2, rows * cell + (rows+1)*2), 255)
    fnt = None
    try:
        fnt = ImageFont.truetype("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 14)
    except:
        pass

    idx = args.index
    for i in range(args.index, end):
        gdata = data[i*128:(i+1)*128]
        im = glyph_to_image(gdata).resize((cell, cell), Image.NEAREST)
        r = (i - args.index) // cols
        c = (i - args.index) % cols
        x = 2 + c * (cell + 2)
        y = 2 + r * (cell + 2)
        grid.paste(im, (x, y))
        if fnt:
            d = ImageDraw.Draw(grid)
            d.text((x + 1, y + cell - 14), f"#{i}", fill=128, font=fnt)

    grid.save(args.out)
    print(f"\nSaved grid PNG → {args.out}  ({cols}×{rows} cells, each glyph 16×16 @4x)")

if __name__ == "__main__":
    main()
