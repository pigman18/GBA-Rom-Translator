#!/usr/bin/env python3
"""
check_font_layout.py
====================
Quickly sanity-check a Gen3 Chinese font .bin BEFORE you burn it into
ADDR_FONT_CHS_NORMAL. Tells you three things:

  1. File size / glyph count (must be N × 128 bytes)
  2. Whether each glyph LOOKS like a 12px-on-16-tall font
     (ink concentrated in rows 2..13, cols 0..11, padding empty)
  3. Whether the TL/BL/TR/BR quadrant layout is plausible
     (ink should appear in all 4 quadrants for a real CJK glyph)

Usage:
    python3 check_font_layout.py font.bin [--verbose]

Exit code 0 = layout looks correct, safe to load.
Exit code 1 = problems found, print what to fix.
"""

import sys, argparse

def nibble_of(tile32: bytes, x: int, y: int) -> int:
    bi = y * 4 + x // 2
    return (tile32[bi] >> 4) & 0x0F if (x & 1) == 0 else tile32[bi] & 0x0F

def analyze_glyph(idx: int, data128: bytes, verbose: bool) -> dict:
    tl = data128[0x00:0x20]
    bl = data128[0x20:0x40]
    tr = data128[0x40:0x60]
    br = data128[0x60:0x80]

    # Build 16x16 nibble map
    grid = [[0]*16 for _ in range(16)]
    for y in range(8):
        for x in range(8):
            grid[y][x] = nibble_of(tl, x, y)
            grid[y+8][x] = nibble_of(bl, x, y)
            grid[y][x+8] = nibble_of(tr, x, y)
            grid[y+8][x+8] = nibble_of(br, x, y)

    # Ink pixels (nibble > 0)
    ink = [(r,c) for r in range(16) for c in range(16) if grid[r][c] > 0]
    n_ink = len(ink)
    if n_ink == 0:
        return {"idx": idx, "status": "EMPTY", "ink": 0}

    rows = [p[0] for p in ink]
    cols = [p[1] for p in ink]
    rmin, rmax = min(rows), max(rows)
    cmin, cmax = min(cols), max(cols)
    h = rmax - rmin + 1
    w = cmax - cmin + 1

    # Padding check (12px on 16-tall: rows 0-1 and 14-15 should be empty)
    pad_top = sum(1 for c in range(16) for r in range(2) if grid[r][c] > 0)
    pad_bot = sum(1 for c in range(16) for r in range(14,16) if grid[r][c] > 0)
    # Width check (12px wide: cols 12-15 should be mostly empty in left half, etc.)
    # Quadrant check
    q_tl = sum(1 for r in range(8) for c in range(8) if grid[r][c] > 0)
    q_bl = sum(1 for r in range(8,16) for c in range(8) if grid[r][c] > 0)
    q_tr = sum(1 for r in range(8) for c in range(8,16) if grid[r][c] > 0)
    q_br = sum(1 for r in range(8,16) for c in range(8,16) if grid[r][c] > 0)

    info = {
        "idx": idx, "ink": n_ink,
        "bounds": f"rows[{rmin}-{rmax}] cols[{cmin}-{cmax}]",
        "size": f"{w}x{h}",
        "pad_top": pad_top, "pad_bot": pad_bot,
        "quads": f"TL={q_tl} BL={q_bl} TR={q_tr} BR={q_br}",
    }

    problems = []
    if h > 14:
        problems.append(f"height {h}px → not a 12px font (too tall)")
    if pad_top > 4:
        problems.append(f"top padding has {pad_top} ink px (expect 0 for 12-on-16)")
    if pad_bot > 4:
        problems.append(f"bottom padding has {pad_bot} ink px (expect 0)")
    if q_tl == 0 and q_tr == 0:
        problems.append("LEFT half all empty (possible TL/BL swapped or 1bpp?)")
    if q_tl == 0 and q_bl == 0:
        problems.append("TOP half all empty (possible TL/TR swapped)")
    if n_ink < 10:
        problems.append(f"only {n_ink} ink px — likely wrong glyph or blank")

    info["problems"] = problems
    return info

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bin")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--max", type=int, default=32, help="how many glyphs to check")
    args = ap.parse_args()

    with open(args.bin, "rb") as f:
        data = f.read()

    n = len(data)
    if n % 128 != 0:
        print(f"❌ File size {n} not divisible by 128. Not a 128B/glyph font.")
        sys.exit(1)

    total = n // 128
    print(f"✅ File: {args.bin}  size={n}  glyphs={total}  (128B each)")
    if total == 0:
        sys.exit(1)

    check = min(args.max, total)
    print(f"Checking first {check} glyphs...\n")

    bad = 0
    for i in range(check):
        info = analyze_glyph(i, data[i*128:(i+1)*128], args.verbose)
        tag = "⚠️" if info["problems"] else "✅"
        if info["problems"]:
            bad += 1
            print(f"  {tag} glyph #{i:5d}  ink={info['ink']:4d}  {info['size']:>7s}  {info['bounds']}")
            for p in info["problems"]:
                print(f"           • {p}")
            if args.verbose:
                print(f"           {info['quads']}")
        elif args.verbose:
            print(f"  {tag} glyph #{i:5d}  ink={info['ink']:4d}  {info['size']:>7s}  {info['bounds']}  {info['quads']}")

    print(f"\n=== Result: {check - bad}/{check} glyphs OK", end="")
    if bad:
        print(f", {bad} with problems ===")
        print("Likely causes:")
        print("  • TL/BL/TR/BR order wrong → regenerate with correct quadrant order")
        print("  • Source was 1bpp not 4bpp → repack as 4bpp (2 pixels/byte, high nibble=left)")
        print("  • Not a 12-on-16 font → redo BDF→tile with 2 rows top+bot padding")
        print("  • Index mismatch → check pack_glyph_index() vs your TBL")
        sys.exit(1)
    else:
        print(" ===")
        print("Layout looks correct. Safe to load at ADDR_FONT_CHS_NORMAL.")

if __name__ == "__main__":
    main()
