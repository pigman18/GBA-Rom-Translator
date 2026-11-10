#!/usr/bin/env python3
"""Export FireRed CN glyphs → deshadowed BDF for AXVJ.

Inputs (default):
  work/_probe/font_final/glyphs.npy   (N,16,16) palette nibbles
  work/_probe/font_final/codes.npy    (N,) FireRed F7 codes
  configs/POKEMON_RUBY_AXVJ00/fonts/normal.bdf  (Unicode match base)

Steps:
  1. Deshadow (ink nibble 12 only) — see firered_font_deshadow.py
  2. Match each FR glyph to an existing normal.bdf Unicode by ink fingerprint
  3. Write BDF; unmatched kept under ENCODING = 0xE000 + (code & 0xFFF)
     with COMMENT fr_code=...

Usage:
  python scripts/firered_export_bdf.py
  python scripts/firered_export_bdf.py --out configs/POKEMON_RUBY_AXVJ00/fonts/normal_firered.bdf
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_chinese_font import parse_bdf, bdf_to_ink  # noqa: E402
from firered_font_deshadow import (  # noqa: E402
    deshadow_matrix,
    ink_bbox,
    mask_to_bdf_hex_rows,
)

SLOT = 16


def normalize_ink(mask: np.ndarray, size: int = 12) -> np.ndarray:
    """Crop ink bbox → nearest-neighbor ``size×size`` binary."""
    bb = ink_bbox(mask)
    out = np.zeros((size, size), dtype=np.uint8)
    if bb is None:
        return out
    x0, y0, x1, y1 = bb
    crop = mask[y0 : y1 + 1, x0 : x1 + 1]
    ch, cw = crop.shape
    for y in range(size):
        for x in range(size):
            sy = min(ch - 1, y * ch // size)
            sx = min(cw - 1, x * cw // size)
            out[y, x] = crop[sy, sx]
    return out


def load_ref_norms(
    bdf_path: Path, ink_w: int = 12, ink_h: int = 12, size: int = 12
) -> list[tuple[int, np.ndarray]]:
    glyphs, ascent, _, _ = parse_bdf(bdf_path)
    out: list[tuple[int, np.ndarray]] = []
    for enc, (bitmap, bw, bh, bx, by) in glyphs.items():
        ink = bdf_to_ink(bitmap, bw, bh, bx, by, ascent, ink_w=ink_w, ink_h=ink_h)
        m = np.array(ink, dtype=np.uint8).reshape(ink_h, ink_w)
        out.append((enc, normalize_ink(m, size=size)))
    return out


def best_unicode(
    norm: np.ndarray,
    ref_enc: np.ndarray,
    ref_mat: np.ndarray,
    used_idx: set[int],
    *,
    max_hamming: int,
) -> tuple[int | None, int, int]:
    """Return (unicode, hamming, ref_index) or (None, best_dist, -1).

    ref_mat: (N, size*size) uint8; used_idx = indices into ref_* already taken.
    """
    flat = norm.reshape(1, -1)
    diffs = np.count_nonzero(ref_mat != flat, axis=1).astype(np.int32)
    if used_idx:
        diffs[list(used_idx)] = 10**9
    i = int(np.argmin(diffs))
    best_d = int(diffs[i])
    if best_d > max_hamming or best_d >= 10**9:
        return None, (best_d if best_d < 10**9 else 999), -1
    return int(ref_enc[i]), best_d, i


def write_bdf(
    entries: list[tuple[int, np.ndarray, str]],
    out: Path,
    *,
    comment: str,
) -> None:
    """entries: (unicode_or_pua, binary 16x16 mask, comment)."""
    lines = [
        "STARTFONT 2.1",
        "FONT -Meowth-FireRed-Medium-R-Normal--16-160-75-75-C-120-ISO10646-1",
        "SIZE 16 75 75",
        "FONTBOUNDINGBOX 16 16 0 -2",
        "STARTPROPERTIES 6",
        "FONT_ASCENT 14",
        "FONT_DESCENT 2",
        "DEFAULT_CHAR 0",
        "PIXEL_SIZE 16",
        f'COMMENT "{comment}"',
        "ENDPROPERTIES",
        f"CHARS {len(entries)}",
        "",
    ]
    for enc, mask, note in entries:
        hex_rows = mask_to_bdf_hex_rows(mask, width=SLOT)
        lines.append(f"STARTCHAR U+{enc:04X}")
        lines.append(f"ENCODING {enc}")
        lines.append("SWIDTH 120 0")
        lines.append("DWIDTH 12 0")
        lines.append("BBX 16 16 0 -2")
        if note:
            lines.append(f'COMMENT "{note}"')
        lines.append("BITMAP")
        lines.extend(hex_rows)
        lines.append("ENDCHAR")
        lines.append("")
    lines.append("ENDFONT")
    lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--glyphs",
        type=Path,
        default=ROOT / "work/_probe/font_final/glyphs.npy",
    )
    ap.add_argument(
        "--codes",
        type=Path,
        default=ROOT / "work/_probe/font_final/codes.npy",
    )
    ap.add_argument(
        "--ref-bdf",
        type=Path,
        default=ROOT / "configs/POKEMON_RUBY_AXVJ00/fonts/normal.bdf",
        help="Unicode match reference (pre-backup original OK)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "configs/POKEMON_RUBY_AXVJ00/fonts/normal_firered.bdf",
    )
    ap.add_argument(
        "--deshadow",
        choices=("ink_only", "drop_adj"),
        default="ink_only",
    )
    ap.add_argument(
        "--preview-dir",
        type=Path,
        default=ROOT / "work/_probe/font_final/deshadow_preview",
    )
    ap.add_argument(
        "--max-hamming",
        type=int,
        default=28,
        help="max Hamming on 12x12 norm for Unicode match (144 bits; 28≈20%%)",
    )
    ap.add_argument(
        "--ink-nibble",
        type=int,
        default=12,
        help="palette nibble treated as ink (font_final=12, smallfont_X=3)",
    )
    ap.add_argument(
        "--shadow-nibble",
        type=int,
        default=1,
        help="palette nibble treated as shadow (font_final=1, smallfont_X=2)",
    )
    ap.add_argument(
        "--place-ink",
        type=int,
        default=0,
        help="if >0, scale deshadowed ink into place_ink×place_ink cell",
    )
    ap.add_argument(
        "--pad-top",
        type=int,
        default=2,
        help="vertical pad when --place-ink is set (small.bdf uses 6)",
    )
    ap.add_argument(
        "--ref-ink",
        type=int,
        default=12,
        help="ref BDF ink size for matching (normal≈12/11, small=9)",
    )
    a = ap.parse_args()

    glyphs = np.load(a.glyphs)
    codes = np.load(a.codes)
    if len(glyphs) != len(codes):
        raise SystemExit(f"len mismatch glyphs={len(glyphs)} codes={len(codes)}")

    print(f"loaded {len(glyphs)} FR glyphs from {a.glyphs}")
    print(f"deshadow mode={a.deshadow} ink_nibble={a.ink_nibble}")

    def prep_mask(mat: np.ndarray) -> np.ndarray:
        mask = deshadow_matrix(
            mat, mode=a.deshadow, ink=a.ink_nibble, shadow=a.shadow_nibble
        )
        if a.place_ink <= 0:
            return mask
        # fit ink bbox into place_ink×place_ink at pad_top
        bb = ink_bbox(mask)
        out = np.zeros((SLOT, SLOT), dtype=np.uint8)
        if bb is None:
            return out
        x0, y0, x1, y1 = bb
        crop = mask[y0 : y1 + 1, x0 : x1 + 1]
        ch, cw = crop.shape
        tw = th = a.place_ink
        scaled = np.zeros((th, tw), dtype=np.uint8)
        for y in range(th):
            for x in range(tw):
                sy = min(ch - 1, y * ch // th)
                sx = min(cw - 1, x * cw // tw)
                scaled[y, x] = crop[sy, sx]
        ox = max(0, (SLOT - tw) // 2)
        oy = max(0, min(SLOT - th, a.pad_top))
        out[oy : oy + th, ox : ox + tw] = scaled
        return out

    # preview first 64
    a.preview_dir.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image

        grid = Image.new("L", (16 * 16, 4 * 16), 0)
        for i in range(min(64, len(glyphs))):
            mask = prep_mask(glyphs[i])
            img = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
            r, c = divmod(i, 16)
            grid.paste(img, (c * 16, r * 16))
        grid.save(a.preview_dir / "first64_ink.png")
        print(f"preview → {a.preview_dir / 'first64_ink.png'}")
    except Exception as e:
        print(f"(preview skipped: {e})")

    print(f"building norms from {a.ref_bdf.name} (ref_ink={a.ref_ink}) …")
    refs = load_ref_norms(
        a.ref_bdf, ink_w=a.ref_ink, ink_h=a.ref_ink, size=a.ref_ink
    )
    ref_enc = np.array([e for e, _ in refs], dtype=np.int32)
    ref_mat = np.stack([m.reshape(-1) for _, m in refs], axis=0)
    print(f"  {len(refs)} reference glyphs")

    used_idx: set[int] = set()
    matched = 0
    entries: list[tuple[int, np.ndarray, str]] = []
    map_rows: list[str] = ["fr_code,unicode,how,hamming"]
    max_h = a.max_hamming

    for code, mat in zip(codes.tolist(), glyphs):
        mask = prep_mask(mat)
        if int(mask.sum()) < 4:
            continue
        norm = normalize_ink(mask, size=a.ref_ink)
        enc, dist, ri = best_unicode(
            norm, ref_enc, ref_mat, used_idx, max_hamming=max_h
        )
        note = f"fr_code=0x{int(code):04X}"
        if enc is not None and ri >= 0:
            used_idx.add(ri)
            matched += 1
            how = "hamming"
            note += f" hamming={dist}"
        else:
            enc = 0xE000 + (int(code) & 0x0FFF)
            how = "pua"
            note += f" unmatched→PUA best_h={dist}"
        entries.append((enc, mask, note))
        map_rows.append(f"0x{int(code):04X},U+{enc:04X},{how},{dist}")

    write_bdf(
        entries,
        a.out,
        comment=(
            f"From FireRed font_final glyphs.npy; deshadow={a.deshadow}; "
            f"matched={matched}/{len(entries)} max_hamming={max_h}"
        ),
    )
    map_path = a.out.with_suffix(".map.csv")
    map_path.write_text("\n".join(map_rows) + "\n", encoding="utf-8")
    print(f"wrote {a.out}  chars={len(entries)}  matched={matched}  "
          f"pua={len(entries) - matched}")
    print(f"map   {map_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
