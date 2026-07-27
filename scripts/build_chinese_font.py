#!/usr/bin/env python3
"""Build Chinese GBA font bins for Gen3 (AXVJ).

Hardware container (fixed):
  Two stacked 8x8 tiles = 8x16 per column; glyph slot = 16x16 (TL,BL,TR,BR).
  128 bytes/glyph, 4bpp. This is NOT optional — same as mature RS CN patches.

12px product metrics (ink / advance / line), NOT a different tile size:
  - Ink ~12x12 inside the 16-tall slot (2px pad top + bottom)
  - CHS_GLYPH_ADVANCE_PX = 12, CHS_CHAR_HEIGHT_PX = 12, CHS_LINE_FEED_PX = 14

Nibble order matches Meowth engine / Font_Patch bins: left pixel = high nibble.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SLOT_W = 16
SLOT_H = 16
INK_W = 12
INK_H = 12
PAD_TOP = 2  # (16-12)/2 — top+bottom pad
BYTES_PER_GLYPH = 128
DEFAULT_GLYPH_COUNT = 7168

_DEFAULT_LEADS = {
    1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 28, 29, 30
}


def lead_adjust(lead: int) -> int:
    adj = lead - 1
    if lead >= 6:
        adj -= 1
    if lead >= 0x1B:
        adj -= 1
    return adj


def glyph_index(lead: int, trail: int) -> int:
    return lead_adjust(lead) * 256 + trail


def parse_charmap(path: Path) -> dict[int, str]:
    mapping: dict[int, str] = {}
    pat = re.compile(r"^([0-9A-Fa-f]+)=(.+)$")
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        m = pat.match(line)
        if not m:
            continue
        hex_val = int(m.group(1), 16)
        char = m.group(2)
        if hex_val <= 0xFF or not char:
            continue
        lead = (hex_val >> 8) & 0xFF
        trail = hex_val & 0xFF
        if lead not in _DEFAULT_LEADS:
            continue
        idx = glyph_index(lead, trail)
        if idx >= DEFAULT_GLYPH_COUNT:
            continue
        mapping[idx] = char
    return mapping


def parse_bdf(path: Path) -> tuple[dict[int, tuple], int, int, int]:
    glyphs: dict[int, tuple] = {}
    font_ascent = 13
    font_descent = 3
    pixel_size = 0
    text = path.read_text("utf-8", errors="replace")
    m = re.search(r"^FONT_ASCENT\s+(\d+)", text, re.MULTILINE)
    if m:
        font_ascent = int(m.group(1))
    m = re.search(r"^FONT_DESCENT\s+(\d+)", text, re.MULTILINE)
    if m:
        font_descent = int(m.group(1))
    m = re.search(r"^PIXEL_SIZE\s+(\d+)", text, re.MULTILINE)
    if m:
        pixel_size = int(m.group(1))

    lines = text.splitlines()
    i, n = 0, len(lines)
    while i < n:
        if lines[i].startswith("STARTCHAR"):
            encoding = 0
            bbx_w = bbx_h = bbx_x = bbx_y = 0
            bitmap: list[bytearray] = []
            i += 1
            while i < n and not lines[i].startswith("BITMAP"):
                l = lines[i]
                if l.startswith("ENCODING"):
                    encoding = int(l.split()[1])
                elif l.startswith("BBX"):
                    parts = l.split()
                    bbx_w, bbx_h, bbx_x, bbx_y = map(int, parts[1:5])
                i += 1
            if i < n:
                i += 1
            while i < n and not lines[i].startswith("ENDCHAR"):
                hex_str = lines[i].strip()
                if hex_str:
                    row_bytes = bytearray()
                    for j in range(0, len(hex_str), 2):
                        row_bytes.append(int(hex_str[j : j + 2], 16))
                    bitmap.append(row_bytes)
                i += 1
            if encoding > 0 and bitmap:
                glyphs[encoding] = (bitmap, bbx_w, bbx_h, bbx_x, bbx_y)
        i += 1
    return glyphs, font_ascent, font_descent, pixel_size


def bdf_to_ink12(
    bitmap_rows: list[bytearray],
    bbx_w: int,
    bbx_h: int,
    bbx_x: int,
    bbx_y: int,
    font_ascent: int,
) -> bytearray:
    """Rasterize BDF into 12x12 ink (1=ink)."""
    src_w = max(bbx_w, 1)
    src_h = len(bitmap_rows) if bitmap_rows else bbx_h
    raw = bytearray(src_w * src_h)
    for y, row in enumerate(bitmap_rows):
        if y >= src_h:
            break
        for x in range(src_w):
            bi, bit = divmod(x, 8)
            if bi < len(row) and (row[bi] & (0x80 >> bit)):
                raw[y * src_w + x] = 1

    min_x, min_y, max_x, max_y = src_w, src_h, -1, -1
    for y in range(src_h):
        for x in range(src_w):
            if raw[y * src_w + x]:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    out = bytearray(INK_W * INK_H)
    if max_x < 0:
        return out
    for y in range(min_y, min(min_y + INK_H, max_y + 1)):
        for x in range(min_x, min(min_x + INK_W, max_x + 1)):
            if raw[y * src_w + x]:
                nx, ny = x - min_x, y - min_y
                if 0 <= nx < INK_W and 0 <= ny < INK_H:
                    out[ny * INK_W + nx] = 1
    return out


def ink12_to_slot16(ink: bytearray, *, shadow: bool) -> bytearray:
    """Place 12x12 ink into 16x16 slot with top/bottom pad. Values 0/14/15."""
    slot = bytearray(SLOT_W * SLOT_H)
    for y in range(INK_H):
        for x in range(INK_W):
            if not ink[y * INK_W + x]:
                continue
            sx, sy = x, y + PAD_TOP
            if not (0 <= sx < SLOT_W and 0 <= sy < SLOT_H):
                continue
            slot[sy * SLOT_W + sx] = 15
            if shadow:
                for dx, dy in ((1, 0), (0, 1), (1, 1)):
                    tx, ty = sx + dx, sy + dy
                    if 0 <= tx < SLOT_W and 0 <= ty < SLOT_H:
                        if slot[ty * SLOT_W + tx] == 0:
                            slot[ty * SLOT_W + tx] = 14
    return slot


def pack_slot16_4bpp(pixels: bytearray) -> bytes:
    """16x16 pixels → 128B TL,BL,TR,BR. Left pixel = high nibble."""
    if len(pixels) != SLOT_W * SLOT_H:
        raise ValueError("slot must be 16x16")
    glyph = bytearray(BYTES_PER_GLYPH)
    for tile_col in range(2):
        for tile_row in range(2):
            tile_idx = tile_col * 2 + tile_row  # TL=0, BL=1, TR=2, BR=3
            off = tile_idx * 32
            for ty in range(8):
                py = tile_row * 8 + ty
                for tx in range(4):
                    px = tile_col * 8 + tx * 2
                    left = pixels[py * SLOT_W + px] & 0x0F
                    right = pixels[py * SLOT_W + px + 1] & 0x0F
                    glyph[off + ty * 4 + tx] = (left << 4) | right
    if len(glyph) != BYTES_PER_GLYPH:
        raise AssertionError(f"pack produced {len(glyph)}, need {BYTES_PER_GLYPH}")
    return bytes(glyph)


def build_font_bin(
    bdf_glyphs: dict,
    charmap: dict[int, str],
    font_ascent: int,
    glyph_count: int = DEFAULT_GLYPH_COUNT,
    bytes_per_glyph: int = BYTES_PER_GLYPH,
    *,
    shadow: bool = True,
) -> bytearray:
    if bytes_per_glyph != BYTES_PER_GLYPH:
        raise ValueError(
            f"bytes_per_glyph must be {BYTES_PER_GLYPH} (16x16 4bpp slot); got {bytes_per_glyph}"
        )
    buf = bytearray(bytes_per_glyph * glyph_count)
    for idx, char in charmap.items():
        encoding = ord(char)
        if encoding in bdf_glyphs:
            bitmap_rows, bbx_w, bbx_h, bbx_x, bbx_y = bdf_glyphs[encoding]
            ink = bdf_to_ink12(bitmap_rows, bbx_w, bbx_h, bbx_x, bbx_y, font_ascent)
        else:
            ink = bytearray(INK_W * INK_H)
        slot = ink12_to_slot16(ink, shadow=shadow)
        packed = pack_slot16_4bpp(slot)
        off = idx * bytes_per_glyph
        buf[off : off + bytes_per_glyph] = packed
    return buf


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build Gen3 Chinese font bins (128B / 16x16 slot, 12px ink)"
    )
    ap.add_argument("--bdf", required=True, type=Path)
    ap.add_argument("--charmap", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--glyph-count", type=int, default=DEFAULT_GLYPH_COUNT)
    ap.add_argument("--bytes-per-glyph", type=int, default=BYTES_PER_GLYPH)
    ap.add_argument("--slot-labels", nargs="+", default=["Normal", "Small"])
    ap.add_argument("--slot-sizes", nargs="+", type=int, default=None)
    ap.add_argument("--prefix", type=str, default="PokeRSFontChs")
    ap.add_argument("--dilate", action="store_true")
    ap.add_argument("--shadow", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--phrase-map", type=Path, default=None)
    args = ap.parse_args()

    if args.bytes_per_glyph != BYTES_PER_GLYPH:
        print(
            f"error: bytes_per_glyph must be {BYTES_PER_GLYPH}, got {args.bytes_per_glyph}",
            file=sys.stderr,
        )
        sys.exit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Parsing BDF: {args.bdf}")
    bdf_glyphs, font_ascent, font_descent, pixel_size = parse_bdf(args.bdf)
    print(
        f"  Loaded {len(bdf_glyphs)} glyphs "
        f"(ascent={font_ascent}, descent={font_descent}, pixel_size={pixel_size})"
    )
    print(
        f"  Target: {INK_W}x{INK_H} ink in {SLOT_W}x{SLOT_H} slot, "
        f"{BYTES_PER_GLYPH} B/glyph, pad_top={PAD_TOP}, shadow={args.shadow}"
    )

    print(f"Parsing charmap: {args.charmap}")
    charmap = parse_charmap(args.charmap)
    print(f"  Found {len(charmap)} Chinese character mappings")

    for i, label in enumerate(args.slot_labels):
        print(f"Building {label} font...")
        buf = build_font_bin(
            bdf_glyphs,
            charmap,
            font_ascent,
            glyph_count=args.glyph_count,
            bytes_per_glyph=args.bytes_per_glyph,
            shadow=args.shadow,
        )
        if args.slot_sizes and i < len(args.slot_sizes):
            buf = buf[: args.slot_sizes[i]]
        slot_size = (
            args.slot_sizes[i]
            if args.slot_sizes and i < len(args.slot_sizes)
            else len(buf)
        )
        fn = f"{args.prefix}{label}(0x{slot_size:X}).bin"
        out_path = args.output_dir / fn
        out_path.write_bytes(buf)
        print(f"  Written {len(buf)} bytes -> {out_path}")
        assert len(buf[0:BYTES_PER_GLYPH]) == 128

    print("Done.")


if __name__ == "__main__":
    main()
