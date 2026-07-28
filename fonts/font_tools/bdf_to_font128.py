#!/usr/bin/env python3
"""
bdf_to_font128.py
==================
Convert a 12x12 (or 12x16) BDF font into the Gen3 128B/glyph layout:

    glyph = TL(32B) + BL(32B) + TR(32B) + BR(32B)   (4bpp, 8x8 tiles)
    ink palette index = 15 (墨), shadow = 14, 0 = transparent
    Padding: ink concentrated in rows 2..13 (12px on 16-tall slot)

Usage:
    python3 bdf_to_font128.py input.bdf output.bin [--shadow]
"""
import sys, argparse, os

def parse_bdf(path):
    """Return dict code -> 12x12 binary rows (each row is 12-bit int, MSB-first)."""
    glyphs = {}
    cur_code = None
    in_bm = False
    rows = []
    with open(path) as f:
        for line in f:
            s = line.strip()
            if s.startswith("ENCODING"):
                if cur_code is not None and len(rows) >= 12:
                    glyphs[cur_code] = rows[:12]
                cur_code = int(s.split()[1])
                rows = []
                in_bm = False
            elif s == "BITMAP":
                in_bm = True
            elif s == "ENDCHAR":
                in_bm = False
            elif in_bm and cur_code is not None:
                rows.append(int(s, 16))
    if cur_code is not None and len(rows) >= 12:
        glyphs[cur_code] = rows[:12]
    return glyphs

def make_128b(glyph_rows12, shadow=False):
    """Take 12 rows of 12-bit each. Return 128 bytes TL+BL+TR+BR 4bpp.
    Layout: ink rows 2..13 of the 16-tall slot; cols 0..11 (right 4 cols empty in each half).
    """
    # Build full 16x12 binary grid (row 0..15, col 0..11)
    grid = [[0]*12 for _ in range(16)]
    for r in range(12):
        val = glyph_rows12[r]
        for c in range(12):
            if (val >> (11 - c)) & 1:
                grid[r + 2][c] = 15  # ink

    def tile_bytes(tile_rows, tile_cols):
        """tile_rows/tile_cols: iter of (row,col) in 8x8 tile, return 32 bytes 4bpp."""
        out = bytearray(32)
        for y in range(8):
            for x in range(8):
                v = grid[tile_rows(y)][tile_cols(x)]
                bi = y * 4 + x // 2
                if x & 1:
                    out[bi] = (out[bi] & 0xF0) | (v & 0x0F)
                else:
                    out[bi] = (out[bi] & 0x0F) | ((v & 0x0F) << 4)
        return bytes(out)

    tl = tile_bytes(lambda y: y,        lambda x: x)       # rows 0..7, cols 0..7
    bl = tile_bytes(lambda y: y + 8,    lambda x: x)       # rows 8..15, cols 0..7
    tr = tile_bytes(lambda y: y,        lambda x: x + 8)    # rows 0..7, cols 8..15  (all 0 here)
    br = tile_bytes(lambda y: y + 8,    lambda x: x + 8)   # rows 8..15, cols 8..15 (all 0 here)
    # Note: 12-wide glyph only uses cols 0..11, so TR/BR tiles are fully zero.
    # This matches the "12px advance, 4px right padding per tile column" rule.
    return tl + bl + tr + br

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bdf")
    ap.add_argument("out")
    ap.add_argument("--first", type=int, default=0x20, help="first code to emit")
    ap.add_argument("--last", type=int, default=0x9FFF, help="last code")
    args = ap.parse_args()

    glyphs = parse_bdf(args.bdf)
    print(f"Loaded {len(glyphs)} glyphs from {args.bdf}")

    # Emit in code order
    codes = sorted(g for g in glyphs if args.first <= g <= args.last)
    print(f"Emitting {len(codes)} glyphs ({codes[0]:#x} .. {codes[-1]:#x})")

    with open(args.out, "wb") as f:
        for c in codes:
            f.write(make_128b(glyphs[c]))

    sz = os.path.getsize(args.out)
    print(f"✅ Wrote {args.out}  ({sz} bytes, {sz//128} glyphs)")
    print(f"   Load at ADDR_FONT_CHS_NORMAL, each glyph = 128B (TL+BL+TR+BR 4bpp)")

if __name__ == "__main__":
    main()
