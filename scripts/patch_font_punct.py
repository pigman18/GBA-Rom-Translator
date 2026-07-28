"""Patch punctuation glyphs into existing font .bin at specific indices.

Positions glyphs using BDF baseline (bbx_y) for correct vertical placement,
unlike build_chinese_font which assumes full-cell CJK and places all ink at
top-left of the 12×12 area.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_chinese_font import (
    parse_bdf, ink12_to_slot16, pack_slot16_4bpp,
    INK_W, INK_H, PAD_TOP, BYTES_PER_GLYPH,
)

def render_bdf_glyph(
    bitmap_rows: list[bytearray],
    bbx_w: int, bbx_h: int, bbx_x: int, bbx_y: int,
    font_ascent: int,
) -> bytearray:
    """Render BDF glyph into 12×12 ink, aligning bottom of visual ink to baseline.

    The original ``bdf_to_ink12`` ignores vertical positioning (places all ink
    at top-left of the 12×12 area).  For punctuation that sits at the baseline
    (comma, period, etc.) this puts them near the top of the slot → wrong.
    Here we find the visual ink extents and place them so the *bottom* of the
    ink aligns with the baseline row (``font_ascent - PAD_TOP``) in the ink area.
    """
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

    if max_x < 0:
        return bytearray(INK_W * INK_H)

    ink_w = max_x - min_x + 1
    ink_h = max_y - min_y + 1
    baseline_ink = font_ascent - PAD_TOP
    dst_top = baseline_ink - ink_h + 1
    if dst_top < 0:
        dst_top = 0

    ink = bytearray(INK_W * INK_H)
    for y in range(ink_h):
        for x in range(ink_w):
            if raw[(min_y + y) * src_w + (min_x + x)]:
                dx = x
                dy = dst_top + y
                if 0 <= dx < INK_W and 0 <= dy < INK_H:
                    ink[dy * INK_W + dx] = 1

    return ink


def patch_font(font_path: Path, charmap_path: Path, bdf_path: Path, *,
               shadow: bool = False) -> None:
    """Patch punctuation glyphs into an existing font .bin at empty slots."""
    bdf_glyphs, font_ascent, _, _ = parse_bdf(bdf_path)

    # ── hardcode slots to patch ─────────────────────────────────────────
    #  lead 0x1E → adjusted glyph index base = lead_adjust(0x1E) << 8 = 27 << 8.
    #  trail 0x5E…0x90 → indices 0x1B5E … 0x1B90.
    PATCH_SLOTS: dict[int, str] = {
        # original 7 punctuation
        0x1B5E: "\uFF0C",   # ，
        0x1B5F: "\u3002",   # 。
        0x1B60: "\uFF01",   # ！
        0x1B61: "\uFF1F",   # ？
        0x1B62: "\uFF1A",   # ：
        0x1B63: "\u3001",   # 、
        0x1B64: "\uFF5E",   # ～
        # corner brackets
        0x1B65: "\u300C",   # 「
        0x1B66: "\u300D",   # 」
        0x1B67: "\u300E",   # 『
        0x1B68: "\u300F",   # 』
        # dots / dash
        0x1B69: "\u2025",   # ‥
        0x1B6A: "\u2026",   # …
        0x1B6B: "\u30FC",   # ー
        # fullwidth punctuation
        0x1B6C: "\uFF08",   # （
        0x1B6D: "\uFF09",   # ）
        0x1B6E: "\u3010",   # 【
        0x1B6F: "\u3011",   # 】
        0x1B70: "\uFF3B",   # ［
        0x1B71: "\uFF3D",   # ］
        0x1B72: "\uFF5B",   # ｛
        0x1B73: "\uFF5D",   # ｝
        # dashes & middle dot
        0x1B74: "\u2014",   # —
        0x1B75: "\u2013",   # –
        0x1B76: "\u00B7",   # ·
        # angle brackets
        0x1B77: "\u300A",   # 《
        0x1B78: "\u300B",   # 》
        # tortoise shell brackets
        0x1B79: "\u3014",   # 〔
        0x1B7A: "\u3015",   # 〕
        # horizontal line
        0x1B7B: "\u2500",   # ─
        # stars
        0x1B7C: "\u2605",   # ★
        0x1B7D: "\u2606",   # ☆
        # arrows
        0x1B7E: "\u2190",   # ←
        0x1B7F: "\u2191",   # ↑
        0x1B80: "\u2192",   # →
        0x1B81: "\u2193",   # ↓
        # geometric shapes
        0x1B82: "\u25A0",   # ■
        0x1B83: "\u25A1",   # □
        0x1B84: "\u25CB",   # ○
        0x1B85: "\u25CF",   # ●
        # math symbols
        0x1B86: "\u2260",   # ≠
        0x1B87: "\u2264",   # ≤
        0x1B88: "\u2265",   # ≥
        # other
        0x1B89: "\u00A7",   # §
        0x1B8A: "\u00B0",   # °
        0x1B8B: "\u203B",   # ※
        # smart quotes
        0x1B8C: "\u2018",   # '
        0x1B8D: "\u2019",   # '
        0x1B8E: "\u201C",   # "
        0x1B8F: "\u201D",   # "
        # katakana middle dot (U+30FB not in SimSun, use U+00B7 glyph)
        0x1B90: "\u30FB",   # ・
    }

    # U+30FB is not in SimSun; fall back to U+00B7 glyph
    BDF_FALLBACK: dict[int, int] = {0x30FB: 0x00B7}

    # ── validate against charmap ───────────────────────────────────────
    pat = re.compile(r"^([0-9A-Fa-f]+)=(.+)$")
    for line in charmap_path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        m = pat.match(line)
        if not m:
            continue
        hex_val = int(m.group(1), 16)
        char = m.group(2)
        lead = (hex_val >> 8) & 0xFF
        trail = hex_val & 0xFF
        if lead == 0x1E and 0x5E <= trail <= 0x64:
            adj = lead - 1
            if lead >= 6:
                adj -= 1
            if lead >= 0x1B:
                adj -= 1
            gidx = (adj << 8) | trail
            expected = chr(ord(char))
            actual = PATCH_SLOTS.get(gidx)
            if actual and actual != char:
                print(f"  WARNING: charmap says {hex_val:04X}={char!r} but hardcode has {actual!r}")

    with open(font_path, 'rb') as f:
        buf = bytearray(f.read())

    patched = 0
    for idx in sorted(PATCH_SLOTS):
        char = PATCH_SLOTS[idx]
        encoding = ord(char)
        off = idx * BYTES_PER_GLYPH
        existing = buf[off:off+BYTES_PER_GLYPH]
        if any(b != 0 for b in existing):
            continue  # slot already has data

        bdf_enc = BDF_FALLBACK.get(encoding, encoding)
        if bdf_enc in bdf_glyphs:
            bitmap_rows, bbx_w, bbx_h, bbx_x, bbx_y = bdf_glyphs[bdf_enc]
            ink = render_bdf_glyph(bitmap_rows, bbx_w, bbx_h, bbx_x, bbx_y, font_ascent)
            if bdf_enc != encoding:
                print(f"  Using fallback U+{bdf_enc:04X} for U+{encoding:04X}")
        else:
            label = char.encode("ascii", errors="replace").decode("ascii")
            print(f"  WARNING: U+{encoding:04X} ({label}) not in BDF, blank")
            ink = bytearray(INK_W * INK_H)

        slot = ink12_to_slot16(ink, shadow=shadow)
        packed = pack_slot16_4bpp(slot)
        buf[off:off+BYTES_PER_GLYPH] = packed
        nz = sum(1 for b in packed if b != 0)
        label = char.encode("ascii", errors="replace").decode("ascii")
        print(f"  Patched {label} (U+{encoding:04X}) @ idx 0x{idx:04X}: {nz}/128")
        patched += 1

    font_path.write_bytes(bytes(buf))
    print(f"\nPatched {patched} glyph(s) -> {font_path}")

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Patch punctuation glyphs into existing font bin")
    ap.add_argument("--font", required=True, type=Path, help="Path to font .bin to patch")
    ap.add_argument("--charmap", required=True, type=Path, help="Path to charmap.txt")
    ap.add_argument("--bdf", required=True, type=Path, help="Path to BDF font")
    ap.add_argument("--no-shadow", dest="shadow", action="store_false", default=False)
    args = ap.parse_args()

    patch_font(args.font, args.charmap, args.bdf, shadow=args.shadow)

if __name__ == "__main__":
    main()
